# Client-Side DOM Morphing

`component-client.js` reconciles the DOM with each server render using
[Idiomorph](https://github.com/bigskysoftware/idiomorph) (vendored unmodified
at `static/component_framework/js/vendor/idiomorph.js`), instead of a full
`innerHTML`/`outerHTML` replace. `update()` (the authoritative server render)
and `rollback()` (restoring a snapshot on request failure) both morph the
component element in place — nodes unaffected by a patch keep their identity,
including attached event listeners, focus, scroll position, and any in-flight
input.

## Opting an element out of morphing: `data-no-morph`

Some DOM regions inside a component are **owned by other JavaScript**, not by
the server render — a third-party widget, a chart/canvas a library draws
into, a manually-mounted rich-text editor, a map instance, and so on.
Idiomorph reconciling that markup on every patch would fight the library (or
destroy state the library keeps on the DOM nodes themselves).

Mark the region's root element with `data-no-morph` and the client will never
touch it, or anything inside it, on either `update()` or `rollback()`:

```html
<div id="component-abc123" data-component="dashboard" data-state='{"range": "7d"}'>
  <button data-event="set_range" data-payload='{"range": "30d"}'>30 days</button>

  <!-- Idiomorph will never morph this element or its descendants, no matter
       what the server sends back for this position in the tree. -->
  <div data-no-morph id="price-chart">
    <canvas></canvas>
  </div>
</div>
```

The attribute's presence is what matters — any value (or none) works.

## Semantics

- **The element and everything inside it is frozen against morphing.**
  Idiomorph's `beforeNodeMorphed` callback returns `false` for a
  `data-no-morph` element (checked via `closest('[data-no-morph]')`, so
  descendants are covered too), which makes idiomorph skip that node
  entirely — it copies no attributes onto it and does not recurse into its
  children. The subtree is left exactly as the DOM has it, byte-for-byte.
- **It also survives being dropped from the server response.** If the
  incoming server HTML has no corresponding node at that position anymore,
  idiomorph would normally remove the old one. The client's
  `beforeNodeRemoved` callback returns `false` for a `data-no-morph` node, so
  it stays attached instead of being deleted.
- **Your server template can keep rendering the element's placeholder markup
  as usual** (e.g. `<div data-no-morph id="price-chart"></div>`) — the client
  never looks at what the server sent for that node's position, so what you
  render there is purely for readability/SSR fallback, not functional.

## Caveats

- **Don't put `data-no-morph` on the component root.** The root element is
  what `update()`/`rollback()` morph against; marking it ignored means the
  component never reconciles with the server again.
- **This is a client-side-only concern.** The server still re-renders the
  region's markup on every dispatch like any other part of the component;
  `data-no-morph` only controls whether the *client* applies that markup to
  the live DOM. If a library needs to persist data across renders, keep that
  data in the library's own state (or the DOM nodes it owns), not in
  server-rendered markup you expect to come back unchanged.
- **Scope it tightly.** Only mark the smallest element that actually needs
  protecting — server-driven interactivity (`[data-event]` triggers, nested
  `[data-component]` children) inside a `data-no-morph` region will never be
  updated by a server patch, since idiomorph never visits that subtree at
  all.
