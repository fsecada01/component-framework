# List Reconciliation Key (`data-key`)

When a component re-renders a list, `component-client.js` morphs the new
markup onto the live DOM in place via
[Idiomorph](https://github.com/bigskysoftware/idiomorph) instead of a full
`innerHTML` replace (see the [README](../README.md) and Epic B, #22). Morphing
preserves node identity — and with it focus, scroll position, in-flight
input, CSS transitions/animations — for nodes idiomorph can match up between
renders.

Idiomorph matches nodes strictly by their real `id` attribute. It has no
config option for a custom reconciliation key. That's fine for content that
doesn't move around, but if a list gets **reordered** between renders (e.g.
sorting, or an item added at the front instead of the end) and the items
don't carry an `id`, idiomorph falls back to matching by tag/position — which
can misattribute a patch meant for one item onto a different item that now
happens to sit in the same slot, discarding that item's DOM state (focus, a
mid-typed value, a running CSS animation) in the process.

## The convention

Give each reorderable list item a stable `data-key`, matching whatever
identifies that item in your data (a primary key, slug, etc.):

```html
<ul id="component-abc123" data-component="task_list" data-state='{"tasks": [...]}'>
  <li data-key="42">Buy milk</li>
  <li data-key="17">Walk the dog</li>
</ul>
```

Before every `Idiomorph.morph()` call, `ComponentClient._bridgeListKeys()`
walks both the live (old) subtree and the incoming server-rendered HTML and
assigns `id="cf-key-<value>"` to any `[data-key]` element that doesn't
already have a real `id`. Idiomorph's own id-based matching then reconciles
`data-key="42"` in the old DOM with `data-key="42"` in the new render,
regardless of where each ended up in the list — reordering, insertions, and
removals all resolve by identity instead of by position.

Elements that already declare a real `id` (e.g. `<li id="task-42"
data-key="42">`) are left untouched — `data-key` only fills the gap when
there's no `id` to match on.

## Notes and limitations

- **The synthesized `id` is not stripped after the morph.** Idiomorph copies
  matched attributes (including `id`) from the new render onto the surviving
  node, so leaving `cf-key-<value>` in place keeps both sides of the next
  update carrying the same id, and idiomorph's own focus-restoration logic
  depends on `id` staying present across the morph. The tradeoff:
  `document.getElementById('cf-key-42')` will resolve to that list item
  elsewhere in the page. Keep `data-key` values unique within the page (not
  just within the list) if you rely on `getElementById` elsewhere, or give
  the element its own real `id` instead of relying on the synthesized one.
- **The incoming HTML is rewritten with a small regex, not a full HTML
  parser** (it hasn't been parsed into a DOM tree yet when the bridge runs —
  idiomorph does that internally). Keep `data-key` values to plain
  identifiers (ids, slugs) and avoid a literal `>` inside another attribute
  on the same tag (e.g. an inline JSON `data-payload` containing `>`), which
  can confuse the tag boundary. Attribute-name matching is anchored to
  whitespace/start-of-attributes (not just a word boundary), so an unrelated
  attribute like `data-id` or `aria-id` won't be mistaken for a real `id`;
  and a literal `"` inside a single-quoted `data-key='...'` value is escaped
  before being re-embedded in the synthesized `id`.
- This only addresses **identity for matching**, not sort order — idiomorph
  still needs to move/reuse the nodes into their new positions, which it
  already does once it can tell old and new nodes apart by id.
