/**
 * Component Framework Client
 *
 * Handles server-side component updates with optimistic UI support.
 * Sends events to the server via fetch, optionally applies a client-side
 * predicted (optimistic) state patch *immediately* — before the request
 * starts — then reconciles the DOM with the authoritative server response.
 * On error the previous DOM state is restored (rollback).
 *
 * Optimistic feedback is opt-in and declarative: a trigger element carries the
 * predicted patch, which `dispatch()` applies synchronously at click time:
 *
 *   - `data-optimistic='{"interested": true}'` — an explicit partial state patch.
 *   - `data-optimistic-toggle="interested"` — shorthand that flips the named
 *     boolean field in the component's current state.
 *
 * The patch is merged into `data-state` and surfaced as `data-optimistic` and
 * `data-optimistic-<field>` attributes so CSS can reflect the pending state
 * instantly. A `[data-loading]` attribute is toggled for the request duration.
 * Ship `component-framework.css` (or your own rules) to style these hooks.
 *
 * Usage:
 *   import { componentClient } from './component-client.js';
 *
 *   // Manual dispatch (optionally with a client-side optimistic patch)
 *   componentClient.dispatch('component-abc123', 'increment', { amount: 1 });
 *   componentClient.dispatch('row-7', 'toggle', {}, { optimistic: { interested: true } });
 *
 *   // Auto-bind declarative markup:
 *   // <div id="component-abc123" data-component="counter"
 *   //      data-state='{"count": 0}' data-endpoint="/components/">
 *   //   <button data-event="increment" data-payload='{"amount": 1}'
 *   //           data-optimistic='{"count": 1}'>+</button>
 *   // </div>
 *
 * JS-owned regions inside a component's rendered subtree (a third-party
 * widget, a manually-mounted JS library instance, a canvas the component
 * doesn't want touched on every patch) can opt out of morphing entirely by
 * carrying a `data-no-morph` attribute:
 *
 *   <div data-no-morph>
 *     <!-- idiomorph will never touch this element or its descendants -->
 *   </div>
 *
 * @module component-client
 */

'use strict';

import { Idiomorph } from './vendor/idiomorph.js';

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

/**
 * Read the CSRF token from the Django session cookie or a <meta> tag.
 *
 * Checks in order:
 *   1. <meta name="csrf-token" content="...">
 *   2. The `csrftoken` cookie (Django default)
 *
 * @returns {string} The CSRF token, or an empty string if not found.
 */
function readCsrfToken() {
  // Meta tag takes precedence (explicit configuration).
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta) {
    return meta.getAttribute('content') || '';
  }

  // Fall back to the Django csrftoken cookie.
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

/**
 * Find the nearest ancestor component element for a given target node.
 * A component element is identified by a `data-component` attribute.
 *
 * @param {Element} target - Starting element for the upward search.
 * @returns {Element|null} The component root element, or null.
 */
function findComponentElement(target) {
  return target.closest('[data-component]') || null;
}

// ---------------------------------------------------------------------------
// ComponentClient
// ---------------------------------------------------------------------------

/**
 * Client for the Component Framework.
 *
 * Manages event dispatch, optimistic UI application, DOM reconciliation,
 * and error rollback for all server-side components on a page.
 */
class ComponentClient {
  /**
   * @param {object} [options={}] - Configuration options.
   * @param {string} [options.endpoint='/components/'] - Default API endpoint.
   * @param {string} [options.csrfToken] - CSRF token. Auto-detected if omitted.
   * @param {function(Error, string): void} [options.onError] - Error callback.
   *   Receives the error and the component ID.
   * @param {function(string, object): void} [options.onUpdate] - Update callback.
   *   Receives the component ID and the server response data.
   */
  constructor(options = {}) {
    this.endpoint = options.endpoint || '/components/';
    this.csrfToken = options.csrfToken || readCsrfToken();
    this.onError = options.onError || null;
    this.onUpdate = options.onUpdate || null;

    /**
     * Rollback snapshots keyed by component ID.
     * Each snapshot holds the previous outerHTML and state so the DOM can be
     * restored on request failure.
     *
     * @type {Map<string, {html: string, state: string|null}>}
     */
    this._snapshots = new Map();

    /**
     * Set of component IDs that are currently awaiting a server response.
     * Used to prevent duplicate concurrent dispatches to the same component.
     *
     * @type {Set<string>}
     */
    this._pending = new Set();
  }

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  /**
   * Send an event to a component and update the DOM.
   *
   * Sequence:
   *   1. Locate the component element by `componentId`.
   *   2. Take a DOM snapshot for potential rollback.
   *   3. If an optimistic patch is supplied, apply it synchronously *now*
   *      (before the request starts) so the UI reflects the predicted state
   *      immediately.
   *   4. POST the event to the server.
   *   5. Replace the component HTML with the authoritative server render,
   *      reconciling (and thereby discarding) the optimistic prediction.
   *   6. On network or server error, roll back to the snapshot and call
   *      `onError` if configured.
   *
   * @param {string} componentId - The `id` attribute of the component element.
   * @param {string} event - Event name to dispatch (e.g. "increment").
   * @param {object} [payload={}] - Arbitrary event payload.
   * @param {object} [options={}] - Dispatch options.
   * @param {object} [options.optimistic] - Predicted partial state patch to
   *   apply immediately (client-side prediction). Reconciled by the server
   *   render on success, rolled back on error.
   * @returns {Promise<object|null>} Server response data, or null on error.
   */
  async dispatch(componentId, event, payload = {}, options = {}) {
    const element = document.getElementById(componentId);
    if (!element) {
      console.warn(`[ComponentClient] Element not found: #${componentId}`);
      return null;
    }

    // Prevent concurrent dispatches to the same component.
    if (this._pending.has(componentId)) {
      console.warn(`[ComponentClient] Dispatch already in progress for #${componentId}`);
      return null;
    }

    // Save snapshot before any mutations.
    this._snapshot(element, componentId);
    this._pending.add(componentId);

    // Apply the client-side optimistic prediction *before* the request so the
    // UI updates instantly. The authoritative server render reconciles it.
    if (options.optimistic) {
      this.applyOptimistic(element, options.optimistic);
    }

    this._markLoading(element, true);

    const componentName = element.dataset.component;
    const stateJson = element.dataset.state || null;
    const endpoint = element.dataset.endpoint || this.endpoint;
    const url = endpoint.endsWith('/') ? `${endpoint}${componentName}/` : `${endpoint}/${componentName}/`;

    const body = {
      event,
      payload,
      ...(stateJson ? { state: stateJson } : {}),
    };

    let data = null;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.csrfToken,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server error ${response.status}: ${errorText}`);
      }

      data = await response.json();

      // Re-acquire the element in case prior optimistic DOM replacement changed it.
      const currentElement = document.getElementById(componentId);
      if (!currentElement) {
        // Element was removed from the DOM during the request; nothing to update.
        return data;
      }

      // Authoritative update: replace DOM with the full server render.
      this.update(currentElement, data.html, data.state);

      if (this.onUpdate) {
        this.onUpdate(componentId, data);
      }
    } catch (err) {
      console.error(`[ComponentClient] Error dispatching "${event}" on #${componentId}:`, err);
      this.rollback(componentId);

      if (this.onError) {
        this.onError(err, componentId);
      }
    } finally {
      this._pending.delete(componentId);
      // Re-acquire element after potential rollback.
      const el = document.getElementById(componentId);
      if (el) {
        this._markLoading(el, false);
      }
    }

    return data;
  }

  /**
   * Apply an optimistic (predicted) state patch to the component element
   * immediately — before the server responds.
   *
   * The patch is merged into the element's `data-state` attribute so that the
   * anticipated state is in place, and the element is marked with
   * `data-optimistic="true"` plus a `data-optimistic-<field>` attribute for
   * each scalar field in the patch.  These attributes give CSS instant styling
   * hooks (e.g. `[data-optimistic-interested="true"]`) without needing a
   * client-side re-render.  The authoritative HTML arrives later via
   * `update()`, which clears these markers.
   *
   * @param {Element} element - The component root element.
   * @param {object} patch - Predicted partial state dict.
   */
  applyOptimistic(element, patch) {
    if (!patch || typeof patch !== 'object') return;

    let currentState = {};
    try {
      currentState = JSON.parse(element.dataset.state || '{}');
    } catch {
      currentState = {};
    }

    const merged = { ...currentState, ...patch };
    element.dataset.state = JSON.stringify(merged);
    element.dataset.optimistic = 'true';

    // Expose scalar predicted values as data-optimistic-<field> attributes so
    // CSS attribute selectors can reflect the pending state instantly.
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || typeof value === 'object') continue;
      element.setAttribute(`data-optimistic-${this._kebab(key)}`, String(value));
    }
  }

  /**
   * Roll back the component element to its last saved snapshot.
   *
   * Called automatically on fetch/server error to undo any speculative DOM
   * mutations.  The rollback morphs the element (in place, via Idiomorph)
   * back to the snapshot's `outerHTML` — which restores the `data-state`
   * attribute too, since it was captured as part of that HTML string.
   * Morphing (rather than a full replace) means nodes unaffected by the
   * rollback keep their identity, including any already-bound event
   * listeners, currently-focused input, and (via the scroll capture/restore
   * below) scroll position.
   *
   * @param {string} componentId - ID of the component to roll back.
   */
  rollback(componentId) {
    const snapshot = this._snapshots.get(componentId);
    if (!snapshot) return;

    const element = document.getElementById(componentId);
    if (!element) return;

    const scrollPositions = this._captureScrollPositions(element);
    Idiomorph.morph(element, snapshot.html, this._morphConfig());
    this._restoreScrollPositions(element, scrollPositions);
    this.bind(element);

    this._snapshots.delete(componentId);
  }

  /**
   * Update the component element with the authoritative server render.
   *
   * Morphs the element (in place, via Idiomorph) to match the new HTML from
   * the server, instead of a full outerHTML replace — nodes unaffected by the
   * update (and their attached listeners) keep their identity. Focus and
   * in-flight input are preserved via the `ignoreActiveValue`/`restoreFocus`
   * morph config (see `_morphConfig()`); scroll position — which idiomorph
   * has no concept of — is preserved via explicit capture/restore around the
   * morph call (see `_captureScrollPositions()`/`_restoreScrollPositions()`).
   * Updates the `data-state` attribute so the next dispatch sends the
   * correct state back, then re-binds declarative event handlers (a no-op
   * for nodes idiomorph preserved, since their listeners already survived
   * the morph; only newly-inserted nodes actually need it).
   *
   * @param {Element} element - The component root element to morph in place.
   * @param {string} html - New component HTML from the server.
   * @param {string|null} [state=null] - Serialized JSON state string.
   */
  update(element, html, state = null) {
    if (!html || !html.trim()) {
      console.warn('[ComponentClient] Server returned empty HTML; skipping update.');
      // The element is not morphed, so clear any optimistic markers we set so
      // the component does not stay visually "pending" forever.
      this._clearOptimistic(element);
      return;
    }

    const scrollPositions = this._captureScrollPositions(element);
    Idiomorph.morph(element, html, this._morphConfig());
    this._restoreScrollPositions(element, scrollPositions);

    // Persist state so subsequent dispatches send the correct value back.
    if (state !== null) {
      element.dataset.state = typeof state === 'string' ? state : JSON.stringify(state);
    }

    // Remove optimistic marker if present.
    delete element.dataset.optimistic;

    // Re-bind declarative handlers (idempotent — see _bindTrigger).
    this.bind(element);
  }

  /**
   * Auto-bind all `[data-component]` elements within `root`.
   *
   * Attaches click and submit handlers to child elements that carry a
   * `data-event` attribute.  The handler calls `dispatch()` with the event
   * name from `data-event` and the JSON payload from `data-payload`.
   *
   * Markup conventions:
   * ```html
   * <div id="component-abc" data-component="counter"
   *      data-state='{"count": 0}' data-endpoint="/components/">
   *
   *   <!-- Click-triggered event -->
   *   <button data-event="increment" data-payload='{"amount": 1}'>+</button>
   *
   *   <!-- Form submit-triggered event -->
   *   <form data-event="submit_form">
   *     <input name="value" type="text" />
   *     <button type="submit">Submit</button>
   *   </form>
   * </div>
   * ```
   *
   * @param {Document|Element} [root=document] - The root element to search within.
   */
  bind(root = document) {
    // Bind each component root.
    const components = root === document
      ? document.querySelectorAll('[data-component]')
      : (root.matches('[data-component]') ? [root] : root.querySelectorAll('[data-component]'));

    for (const componentEl of components) {
      const componentId = componentEl.id;
      if (!componentId) {
        console.warn('[ComponentClient] Component element missing id attribute:', componentEl);
        continue;
      }

      // Bind interactive children.
      const triggers = componentEl.querySelectorAll('[data-event]');
      for (const trigger of triggers) {
        this._bindTrigger(trigger, componentId);
      }
    }
  }

  // -------------------------------------------------------------------------
  // Private helpers
  // -------------------------------------------------------------------------

  /**
   * Attach the appropriate DOM event listener to a trigger element.
   *
   * Form elements listen on `submit`; all other elements listen on `click`.
   * The handler is stored via a WeakMap-compatible closure approach: the
   * element's `_cfHandler` property caches the bound function so it can be
   * removed before re-binding (prevents duplicate handlers after DOM updates).
   *
   * @param {Element} trigger - Element carrying `data-event`.
   * @param {string} componentId - ID of the parent component element.
   */
  _bindTrigger(trigger, componentId) {
    const eventName = trigger.dataset.event;
    if (!eventName) return;

    // Remove previous handler to avoid duplicates.
    if (trigger._cfHandler) {
      const domEvent = trigger.tagName === 'FORM' ? 'submit' : 'click';
      trigger.removeEventListener(domEvent, trigger._cfHandler);
    }

    const isForm = trigger.tagName === 'FORM';
    const domEvent = isForm ? 'submit' : 'click';

    const handler = (domEventObj) => {
      domEventObj.preventDefault();

      let payload = {};
      try {
        payload = JSON.parse(trigger.dataset.payload || '{}');
      } catch {
        payload = {};
      }

      // For forms, merge serialized form data into the payload.
      if (isForm) {
        const formData = new FormData(trigger);
        for (const [key, value] of formData.entries()) {
          payload[key] = value;
        }
      }

      const optimistic = this._computeOptimistic(trigger, componentId);
      this.dispatch(componentId, eventName, payload, optimistic ? { optimistic } : {});
    };

    trigger._cfHandler = handler;
    trigger.addEventListener(domEvent, handler);
  }

  /**
   * Compute a client-side optimistic patch for a trigger, if declared.
   *
   * Supports two declarative forms on the trigger element:
   *   - `data-optimistic='{"field": value, ...}'` — an explicit partial patch.
   *   - `data-optimistic-toggle="field"` — flips the named boolean field based
   *     on the component's current `data-state`.
   *
   * @param {Element} trigger - The element carrying the declarative attributes.
   * @param {string} componentId - ID of the parent component element.
   * @returns {object|null} The predicted patch, or null if none declared.
   */
  _computeOptimistic(trigger, componentId) {
    // Explicit patch takes precedence.
    if (trigger.dataset.optimistic) {
      try {
        const patch = JSON.parse(trigger.dataset.optimistic);
        if (patch && typeof patch === 'object') return patch;
      } catch {
        console.warn('[ComponentClient] Invalid data-optimistic JSON:', trigger.dataset.optimistic);
      }
      return null;
    }

    // Toggle shorthand: flip a boolean field in the current component state.
    const field = trigger.dataset.optimisticToggle;
    if (field) {
      const element = document.getElementById(componentId);
      let state = {};
      try {
        state = JSON.parse((element && element.dataset.state) || '{}');
      } catch {
        state = {};
      }
      return { [field]: !state[field] };
    }

    return null;
  }

  /**
   * Build the `Idiomorph.morph()` config shared by `update()` and
   * `rollback()`.
   *
   * Wires two Epic B (#22) concerns into one shared config:
   *   - **B2**: `ignoreActiveValue: true` preserves in-flight input — without
   *     it, idiomorph overwrites the currently-focused element's `value`
   *     with whatever the server rendered, clobbering keystrokes made while
   *     the request was in flight. (Focus itself is preserved for free via
   *     idiomorph's own `restoreFocus` default — see `vendor/idiomorph.js`.)
   *     Scroll position, also a B2 concern, is deliberately NOT part of this
   *     config — idiomorph has no concept of scroll at all, so it's handled
   *     separately via explicit capture/restore around each morph call (see
   *     `_captureScrollPositions()`/`_restoreScrollPositions()`).
   *   - **B4**: the "don't morph this" escape hatch — any element carrying a
   *     `data-no-morph` attribute, and by extension everything inside it, is
   *     left completely untouched by the morph, so JS-owned DOM regions (a
   *     third-party widget, a manually-mounted JS library instance, a
   *     canvas, etc.) survive server patches unchanged. `beforeNodeMorphed`
   *     returning `false` makes idiomorph skip the node entirely — it
   *     neither copies attributes onto it nor recurses into its children, so
   *     descendants are protected too without needing their own check.
   *     `beforeNodeRemoved` returning `false` additionally stops idiomorph
   *     from deleting an ignored node outright when the incoming server HTML
   *     has no corresponding node at that position.
   *
   * @returns {object} The config object to pass as `Idiomorph.morph()`'s
   *   third argument.
   */
  _morphConfig() {
    return {
      morphStyle: 'outerHTML',
      ignoreActiveValue: true,
      callbacks: {
        beforeNodeMorphed: (oldNode) => !this._isIgnoredNode(oldNode),
        beforeNodeRemoved: (node) => !this._isIgnoredNode(node),
      },
    };
  }

  /**
   * Whether `node` (or one of its ancestors) carries the `data-no-morph`
   * escape-hatch attribute.
   *
   * Uses `closest()` rather than checking `node` alone so the whole subtree
   * rooted at a `data-no-morph` element is protected, not just that
   * element's own attributes. Non-element nodes (e.g. text nodes passed to
   * idiomorph's callbacks) don't expose `closest()`; treat those as never
   * ignored rather than throwing.
   *
   * @param {Node} node - The node idiomorph is about to morph or remove.
   * @returns {boolean} True if the node must be left untouched.
   */
  _isIgnoredNode(node) {
    if (!node || typeof node.closest !== 'function') return false;
    return node.closest('[data-no-morph]') !== null;
  }

  /**
   * Convert a camelCase or snake_case key to kebab-case for use in a
   * `data-optimistic-<field>` attribute name.
   *
   * @param {string} key - State field name.
   * @returns {string} The kebab-cased attribute fragment.
   */
  _kebab(key) {
    return String(key)
      .replace(/_/g, '-')
      .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
      .toLowerCase();
  }

  /**
   * Remove optimistic styling markers (`data-optimistic` and every
   * `data-optimistic-<field>`) from an element in place.  Normally these
   * markers vanish because `update()`/`rollback()` replace the whole element;
   * this is the fallback for paths where the element survives (e.g. an empty
   * server render) so the component does not remain visually pending.
   *
   * @param {Element} element - The component root element.
   */
  _clearOptimistic(element) {
    if (!element) return;
    delete element.dataset.optimistic;
    for (const name of element.getAttributeNames()) {
      if (name.startsWith('data-optimistic-')) {
        element.removeAttribute(name);
      }
    }
  }

  /**
   * Capture scroll offsets that would otherwise be lost when idiomorph
   * recreates a scrollable element instead of patching it in place.
   * Idiomorph has no concept of scroll position at all — this is bespoke
   * bookkeeping this framework owns around `Idiomorph.morph()`, not morph
   * configuration.
   *
   * Only the root element and descendants carrying a stable `id` can be
   * re-located after the morph (mirrors idiomorph's own `restoreFocus`,
   * which likewise needs an `id` to re-find a recreated focused element), and
   * only non-zero offsets are recorded, to keep the common case a no-op.
   *
   * @param {Element} element - The component root element about to be morphed.
   * @returns {Array<{id: string|null, isRoot: boolean, top: number, left: number}>}
   *   Captured offsets to pass to `_restoreScrollPositions()`.
   */
  _captureScrollPositions(element) {
    const positions = [];

    const record = (el, isRoot) => {
      const top = el.scrollTop || 0;
      const left = el.scrollLeft || 0;
      if (!top && !left) return;
      positions.push({ id: isRoot ? null : el.id || null, isRoot, top, left });
    };

    record(element, true);
    if (typeof element.querySelectorAll === 'function') {
      for (const el of element.querySelectorAll('[id]')) {
        record(el, false);
      }
    }

    return positions;
  }

  /**
   * Restore scroll offsets captured by `_captureScrollPositions()` after a
   * morph. The root element keeps its identity across an outerHTML morph
   * (see `update()`/`rollback()`), so it is restored via the direct
   * reference; descendants are re-located by `id`, since idiomorph may have
   * recreated rather than patched them. Descendants with no `id` cannot be
   * re-located and are silently skipped — a documented limitation shared
   * with idiomorph's own focus restoration.
   *
   * @param {Element} element - The component root element that was morphed.
   * @param {Array<{id: string|null, isRoot: boolean, top: number, left: number}>} positions
   *   Offsets returned by `_captureScrollPositions()`.
   */
  _restoreScrollPositions(element, positions) {
    for (const pos of positions) {
      let target = null;
      if (pos.isRoot) {
        target = element;
      } else if (pos.id && typeof element.querySelector === 'function') {
        target = element.querySelector(`[id="${pos.id}"]`);
      }
      if (target) {
        target.scrollTop = pos.top;
        target.scrollLeft = pos.left;
      }
    }
  }

  /**
   * Save a DOM snapshot for `componentId` before any mutation.
   *
   * @param {Element} element - The component root element.
   * @param {string} componentId - Component ID used as the snapshot key.
   */
  _snapshot(element, componentId) {
    this._snapshots.set(componentId, {
      html: element.outerHTML,
      state: element.dataset.state || null,
    });
  }

  /**
   * Toggle a `data-loading` attribute on the component element to allow CSS
   * styling during in-flight requests.
   *
   * @param {Element} element - The component root element.
   * @param {boolean} isLoading - Whether the component is currently loading.
   */
  _markLoading(element, isLoading) {
    if (isLoading) {
      element.dataset.loading = 'true';
    } else {
      delete element.dataset.loading;
    }
  }
}

// ---------------------------------------------------------------------------
// Default instance & auto-init
// ---------------------------------------------------------------------------

/**
 * Singleton ComponentClient instance used by the default auto-binding.
 * Import and use this directly for most use cases.
 *
 * @type {ComponentClient}
 */
const componentClient = new ComponentClient();

document.addEventListener('DOMContentLoaded', () => {
  componentClient.bind();
});

export { ComponentClient, componentClient };
