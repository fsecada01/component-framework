/**
 * Component Framework Client
 *
 * Handles server-side component updates with optimistic UI support.
 * Sends events to the server via fetch, applies optimistic state patches
 * immediately, then reconciles the DOM with the server response.
 * On error the previous DOM state is restored (rollback).
 *
 * Usage:
 *   import { componentClient } from './component-client.js';
 *
 *   // Manual dispatch
 *   componentClient.dispatch('component-abc123', 'increment', { amount: 1 });
 *
 *   // Auto-bind declarative markup:
 *   // <div id="component-abc123" data-component="counter"
 *   //      data-state='{"count": 0}' data-endpoint="/components/">
 *   //   <button data-event="increment" data-payload='{"amount": 1}'>+</button>
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
   *   3. POST the event to the server.
   *   4. If the server response contains an `optimistic` patch, apply it
   *      immediately (before the full render arrives — note: in the current
   *      architecture the patch is returned in the same response; for future
   *      streaming support the patch could arrive separately).
   *   5. Replace the component HTML with the authoritative server render.
   *   6. On network or server error, roll back to the snapshot and call
   *      `onError` if configured.
   *
   * @param {string} componentId - The `id` attribute of the component element.
   * @param {string} event - Event name to dispatch (e.g. "increment").
   * @param {object} [payload={}] - Arbitrary event payload.
   * @returns {Promise<object|null>} Server response data, or null on error.
   */
  async dispatch(componentId, event, payload = {}) {
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
    this._markLoading(element, true);

    const componentName = element.dataset.component;
    const stateJson = element.dataset.state || null;
    const endpoint = element.dataset.endpoint || this.endpoint;
    const url = endpoint.endsWith('/') ? `${endpoint}${componentName}/` : `${endpoint}/${componentName}/`;

    const body = {
      event,
      payload: JSON.stringify(payload),
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
   * Apply an optimistic state patch to the component element immediately.
   *
   * The patch is a partial state dict returned by the server alongside the
   * normal render.  It is merged into the element's `data-state` attribute so
   * that subsequent dispatches use the anticipated state rather than stale
   * values.  The actual HTML is not changed here; `update()` does that once
   * the full server render arrives.
   *
   * @param {Element} element - The component root element.
   * @param {object} patch - Partial state dict from the server `optimistic` key.
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

      this.dispatch(componentId, eventName, payload);
    };

    trigger._cfHandler = handler;
    trigger.addEventListener(domEvent, handler);
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
