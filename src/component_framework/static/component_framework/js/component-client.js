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
 * @module component-client
 */

'use strict';

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
   * mutations.  The rollback restores both the `outerHTML` (replacing the
   * element in the DOM) and the `data-state` attribute.
   *
   * @param {string} componentId - ID of the component to roll back.
   */
  rollback(componentId) {
    const snapshot = this._snapshots.get(componentId);
    if (!snapshot) return;

    const element = document.getElementById(componentId);
    if (!element) return;

    // Build a temporary wrapper to parse the snapshot HTML back into a node.
    const wrapper = document.createElement('div');
    wrapper.innerHTML = snapshot.html;
    const restoredNode = wrapper.firstElementChild;

    if (restoredNode) {
      element.replaceWith(restoredNode);
    }

    this._snapshots.delete(componentId);
  }

  /**
   * Update the component element with the authoritative server render.
   *
   * Replaces the element's `outerHTML` with the new HTML from the server and
   * updates the `data-state` attribute so the next dispatch sends the correct
   * state back.  After updating, declarative event bindings are re-attached to
   * any new child elements.
   *
   * @param {Element} element - The component root element to replace.
   * @param {string} html - New component HTML from the server.
   * @param {string|null} [state=null] - Serialized JSON state string.
   */
  update(element, html, state = null) {
    // Build the new DOM node from the server HTML.
    const wrapper = document.createElement('div');
    wrapper.innerHTML = html;
    const newNode = wrapper.firstElementChild;

    if (!newNode) {
      console.warn('[ComponentClient] Server returned empty HTML; skipping update.');
      return;
    }

    // Persist state on the new node so subsequent dispatches work correctly.
    if (state !== null) {
      newNode.dataset.state = typeof state === 'string' ? state : JSON.stringify(state);
    }

    // Remove optimistic marker if present.
    delete newNode.dataset.optimistic;

    // Swap the old element for the new one.
    element.replaceWith(newNode);

    // Re-bind declarative handlers on the newly inserted subtree.
    this.bind(newNode);
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
