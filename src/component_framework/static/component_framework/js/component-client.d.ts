/**
 * TypeScript type declarations for the Component Framework Client.
 *
 * @module component-client
 */

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

/** Configuration options accepted by the {@link ComponentClient} constructor. */
export interface ComponentClientOptions {
  /**
   * Default API endpoint prefix used when a component element does not specify
   * its own `data-endpoint` attribute.
   *
   * @default '/components/'
   */
  endpoint?: string;

  /**
   * CSRF token sent in the `X-CSRFToken` request header.
   * When omitted the client tries to auto-detect the token from a
   * `<meta name="csrf-token">` element or the `csrftoken` cookie.
   */
  csrfToken?: string;

  /**
   * Called when a dispatch request fails (network error or non-2xx HTTP
   * status).  Receives the thrown error and the component ID that was being
   * updated.
   */
  onError?: (error: Error, componentId: string) => void;

  /**
   * Called after a successful server response has been applied to the DOM.
   * Receives the component ID and the full parsed server response object.
   */
  onUpdate?: (componentId: string, data: ComponentResponse) => void;
}

// ---------------------------------------------------------------------------
// Server response shape
// ---------------------------------------------------------------------------

/**
 * JSON object returned by the server after dispatching a component event.
 */
export interface ComponentResponse {
  /** Full rendered HTML for the component. */
  html: string;

  /** Serialized JSON state string (ready to store in `data-state`). */
  state: string;

  /** Server-assigned component identifier. */
  component_id: string;

  /**
   * Optional optimistic state patch.
   *
   * Present when the component's `get_optimistic_patch()` returned a non-None
   * value.  Because it is delivered alongside the full render it does not by
   * itself produce instant feedback; for that, declare `data-optimistic` on the
   * trigger (see {@link DispatchOptions}).  It is exposed here for inspection
   * via the `onUpdate` callback and for forward streaming support.
   */
  optimistic?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Dispatch options
// ---------------------------------------------------------------------------

/** Per-call options for {@link ComponentClient.dispatch}. */
export interface DispatchOptions {
  /**
   * Predicted partial state patch applied synchronously *before* the request
   * starts (client-side prediction), then reconciled by the authoritative
   * server render on success or rolled back on error.
   */
  optimistic?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// DOM snapshot
// ---------------------------------------------------------------------------

/** Internal DOM snapshot stored before each dispatch for rollback support. */
export interface DomSnapshot {
  /** `outerHTML` of the component element before the dispatch. */
  html: string;

  /** `data-state` attribute value before the dispatch, or `null` if absent. */
  state: string | null;
}

// ---------------------------------------------------------------------------
// ComponentClient
// ---------------------------------------------------------------------------

/**
 * Client for the Component Framework.
 *
 * Manages event dispatch, optimistic UI patch application, DOM
 * reconciliation, and error rollback for server-side components.
 *
 * @example
 * ```ts
 * import { componentClient } from './component-client.js';
 *
 * // Manual dispatch
 * await componentClient.dispatch('component-abc123', 'increment', { amount: 1 });
 *
 * // Declarative auto-binding happens automatically on DOMContentLoaded.
 * ```
 */
export declare class ComponentClient {
  /** Default API endpoint prefix. */
  endpoint: string;

  /** CSRF token sent in the `X-CSRFToken` header. */
  csrfToken: string;

  /** Optional error callback. */
  onError: ((error: Error, componentId: string) => void) | null;

  /** Optional update callback. */
  onUpdate: ((componentId: string, data: ComponentResponse) => void) | null;

  constructor(options?: ComponentClientOptions);

  /**
   * Send an event to a component and update the DOM.
   *
   * When `options.optimistic` is supplied, applies the predicted patch
   * synchronously *before* the request starts, then replaces the component HTML
   * with the authoritative server render.  On failure the DOM is rolled back to
   * the pre-dispatch snapshot.
   *
   * @param componentId - The `id` attribute of the target component element.
   * @param event - Event name to dispatch (e.g. `"increment"`).
   * @param payload - Arbitrary event payload object.
   * @param options - Per-call dispatch options (e.g. an optimistic patch).
   * @returns The parsed server response, or `null` on error or missing element.
   */
  dispatch(
    componentId: string,
    event: string,
    payload?: Record<string, unknown>,
    options?: DispatchOptions,
  ): Promise<ComponentResponse | null>;

  /**
   * Apply a predicted optimistic patch to the component element immediately:
   * merges it into `data-state` and sets `data-optimistic` /
   * `data-optimistic-<field>` attributes as CSS styling hooks.
   *
   * @param element - The component root element.
   * @param patch - Predicted partial state dict.
   */
  applyOptimistic(element: Element, patch: Record<string, unknown>): void;

  /**
   * Restore the component element to its pre-dispatch snapshot on error.
   *
   * @param componentId - ID of the component to roll back.
   */
  rollback(componentId: string): void;

  /**
   * Replace the component element with the authoritative HTML from the server
   * and update its `data-state` attribute.
   *
   * @param element - The component root element to replace.
   * @param html - Full component HTML returned by the server.
   * @param state - Serialized JSON state string, or `null`.
   */
  update(element: Element, html: string, state?: string | null): void;

  /**
   * Auto-bind all `[data-component]` elements within `root`.
   *
   * Attaches click/submit handlers to child `[data-event]` elements so that
   * interactions are wired up declaratively without manual JavaScript.
   *
   * @param root - Root element (or `document`) to search for component
   *   elements.  Defaults to `document`.
   */
  bind(root?: Document | Element): void;
}

// ---------------------------------------------------------------------------
// Default singleton instance
// ---------------------------------------------------------------------------

/**
 * Pre-created {@link ComponentClient} instance.
 *
 * This instance is used by the auto-binding that runs on `DOMContentLoaded`.
 * Import and use it directly for the most common use-cases.
 *
 * @example
 * ```ts
 * import { componentClient } from './component-client.js';
 * await componentClient.dispatch('my-component', 'click');
 * ```
 */
export declare const componentClient: ComponentClient;
