/**
 * Node-native tests for the "don't morph this" escape hatch in
 * component-client.js (Epic B, B4 — #22).
 *
 * Run with: node --test "tests/js/**\/*.test.mjs"
 *   (`just test-js` has a pre-existing cmd.exe glob-expansion bug on Windows;
 *   use the raw node command instead — see PR #43.)
 *
 * Convention: an element carrying the `data-no-morph` attribute (any value,
 * presence is enough) tells the client "idiomorph must never touch this
 * element or its descendants" — for a third-party widget, a manually-mounted
 * JS library instance, a canvas, etc. that a component doesn't want
 * clobbered on every server patch.
 *
 * Scope note (consistent with morph.test.mjs's stated philosophy): idiomorph
 * itself ships its own upstream test suite and is vendored unmodified, so we
 * don't re-verify idiomorph's own internals here. Instead we verify the
 * *integration seam* — that update()/rollback() wire a `beforeNodeMorphed`
 * (and `beforeNodeRemoved`) callback into the Idiomorph.morph() config, and
 * that the callback correctly identifies `data-no-morph` elements and their
 * descendants. The resulting behaviour when idiomorph *runs* those callbacks
 * was confirmed by direct source read of vendor/idiomorph.js:
 *
 *   - morphNode() (~line 645): `if (ctx.callbacks.beforeNodeMorphed(oldNode,
 *     newContent) === false) { return oldNode; }` — the function returns
 *     immediately, *before* morphAttributes() or morphChildren() are called
 *     and *before* afterNodeMorphed() fires. So returning `false` protects
 *     the node's own attributes AND skips recursing into its children
 *     entirely — the whole subtree is left untouched, not just the root's
 *     attributes.
 *   - removeNode() (~line 528): `if (ctx.callbacks.beforeNodeRemoved(node)
 *     === false) return;` — the node is not removed from the DOM if the
 *     incoming server HTML has no matching node at that position.
 */

import assert from 'node:assert/strict';
import { test } from 'node:test';

// --- Minimal DOM stubs (installed before importing the module) ------------

/**
 * A tiny Element-ish stub that supports enough of the real DOM API for
 * `closest('[data-no-morph]')`-style ancestor lookups, without pulling in a
 * full DOM implementation (this repo has no jsdom dependency — see
 * morph.test.mjs / optimistic.test.mjs).
 */
function makeNode({ attrs = {}, parent = null } = {}) {
  return {
    nodeType: 1,
    _attrs: { ...attrs },
    _parent: parent,
    hasAttribute(name) {
      return name in this._attrs;
    },
    getAttribute(name) {
      return name in this._attrs ? this._attrs[name] : null;
    },
    closest(selector) {
      const match = /^\[([\w-]+)\]$/.exec(selector);
      const attrName = match ? match[1] : null;
      let node = this;
      while (node) {
        if (attrName && node.hasAttribute(attrName)) return node;
        node = node._parent;
      }
      return null;
    },
  };
}

// A Text-node-like stub: no `closest`, mirroring real DOM Text nodes.
function makeTextNode() {
  return { nodeType: 3 };
}

function makeEl(dataset = {}, extra = {}) {
  return {
    dataset,
    id: extra.id ?? 'c1',
    tagName: extra.tagName ?? 'DIV',
    outerHTML: extra.outerHTML ?? '<div></div>',
    _attrs: {},
    _replacedWith: null,
    setAttribute(k, v) {
      this._attrs[k] = v;
    },
    getAttribute(k) {
      return k in this._attrs ? this._attrs[k] : null;
    },
    getAttributeNames() {
      return Object.keys(this._attrs);
    },
    removeAttribute(k) {
      delete this._attrs[k];
    },
    replaceWith(n) {
      this._replacedWith = n;
    },
    closest() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    matches() {
      return false;
    },
  };
}

const registry = {};
globalThis.document = {
  querySelector: () => null,
  cookie: '',
  getElementById: (id) => registry[id] ?? null,
  addEventListener: () => {},
  createElement: () => makeEl({}),
};

const { ComponentClient } = await import(
  '../../src/component_framework/static/component_framework/js/component-client.js'
);
const { Idiomorph } = await import(
  '../../src/component_framework/static/component_framework/js/vendor/idiomorph.js'
);

/** Capture the config idiomorph would have been called with. */
function captureMorphConfig(run) {
  let morphArgs = null;
  const originalMorph = Idiomorph.morph;
  Idiomorph.morph = (...args) => {
    morphArgs = args;
  };
  try {
    run();
  } finally {
    Idiomorph.morph = originalMorph;
  }
  return morphArgs;
}

// --- Tests ------------------------------------------------------------------

test('update() wires a beforeNodeMorphed callback into the Idiomorph.morph config', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' });
  registry.c1 = el;

  const morphArgs = captureMorphConfig(() => {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  });

  assert.ok(morphArgs, 'Idiomorph.morph should have been called');
  assert.equal(
    typeof morphArgs[2].callbacks?.beforeNodeMorphed,
    'function',
    'a beforeNodeMorphed callback must be present in the morph config',
  );
  delete registry.c1;
});

test('beforeNodeMorphed returns false for an element carrying data-no-morph', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' });
  registry.c1 = el;

  const morphArgs = captureMorphConfig(() => {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  });

  const ignored = makeNode({ attrs: { 'data-no-morph': '' } });
  const newContent = makeNode({});
  assert.equal(
    morphArgs[2].callbacks.beforeNodeMorphed(ignored, newContent),
    false,
    'a data-no-morph element must be skipped by the morph',
  );
  delete registry.c1;
});

test('beforeNodeMorphed also protects descendants of an ignored ancestor', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' });
  registry.c1 = el;

  const morphArgs = captureMorphConfig(() => {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  });

  const ignoredAncestor = makeNode({ attrs: { 'data-no-morph': '' } });
  const child = makeNode({ parent: ignoredAncestor });
  const grandchild = makeNode({ parent: child });

  assert.equal(morphArgs[2].callbacks.beforeNodeMorphed(child, makeNode({})), false);
  assert.equal(morphArgs[2].callbacks.beforeNodeMorphed(grandchild, makeNode({})), false);
  delete registry.c1;
});

test('beforeNodeMorphed does not skip ordinary elements', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' });
  registry.c1 = el;

  const morphArgs = captureMorphConfig(() => {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  });

  const ordinary = makeNode({});
  assert.notEqual(morphArgs[2].callbacks.beforeNodeMorphed(ordinary, makeNode({})), false);
  delete registry.c1;
});

test('beforeNodeMorphed does not throw for a text node (no closest())', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' });
  registry.c1 = el;

  const morphArgs = captureMorphConfig(() => {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  });

  const text = makeTextNode();
  assert.doesNotThrow(() => morphArgs[2].callbacks.beforeNodeMorphed(text, makeNode({})));
  assert.notEqual(morphArgs[2].callbacks.beforeNodeMorphed(text, makeNode({})), false);
  delete registry.c1;
});

test('update() wires a beforeNodeRemoved callback that protects data-no-morph nodes from removal', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' });
  registry.c1 = el;

  const morphArgs = captureMorphConfig(() => {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  });

  assert.equal(
    typeof morphArgs[2].callbacks?.beforeNodeRemoved,
    'function',
    'a beforeNodeRemoved callback must be present in the morph config',
  );

  const ignored = makeNode({ attrs: { 'data-no-morph': '' } });
  assert.equal(
    morphArgs[2].callbacks.beforeNodeRemoved(ignored),
    false,
    'a data-no-morph node must not be removed even if absent from new content',
  );

  const ordinary = makeNode({});
  assert.notEqual(morphArgs[2].callbacks.beforeNodeRemoved(ordinary), false);
  delete registry.c1;
});

test('rollback() wires the same ignore-aware callbacks into the Idiomorph.morph config', () => {
  const client = new ComponentClient();
  const el = makeEl(
    { state: '{"count":2}' },
    { outerHTML: '<div id="c1" data-state=\'{"count":1}\'>1</div>' },
  );
  registry.c1 = el;
  client._snapshot(el, 'c1');

  const morphArgs = captureMorphConfig(() => {
    client.rollback('c1');
  });

  assert.ok(morphArgs, 'Idiomorph.morph should have been called');
  const ignored = makeNode({ attrs: { 'data-no-morph': '' } });
  assert.equal(morphArgs[2].callbacks.beforeNodeMorphed(ignored, makeNode({})), false);
  assert.equal(morphArgs[2].callbacks.beforeNodeRemoved(ignored), false);
  delete registry.c1;
});

test('morphStyle is still outerHTML after adding the ignore-region callbacks', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' });
  registry.c1 = el;

  const morphArgs = captureMorphConfig(() => {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  });

  assert.equal(morphArgs[2].morphStyle, 'outerHTML');
  delete registry.c1;
});
