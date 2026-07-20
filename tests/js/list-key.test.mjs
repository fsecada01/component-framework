/**
 * Node-native tests for the `data-key` list-reconciliation bridge in
 * component-client.js (Epic B, B3 — #22).
 *
 * Run with: node --test "tests/js/**\/*.test.mjs"   (see morph.test.mjs for
 * why not `just test-js` on Windows)
 *
 * Idiomorph matches nodes strictly by their real `id` attribute
 * (`createIdMaps`/`populateIdMapWithTree` in vendor/idiomorph.js do
 * `root.querySelectorAll("[id]")` — there is no config option for a custom
 * key). So a `data-key` convention can't just be a morph config flag; it
 * needs a small preprocessing pass that bridges `data-key` values onto a
 * real `id` (synthesized as `cf-key-<value>`, consistent with this file's
 * existing `cf-` prefix convention — see `_cfHandler` — and CSS's
 * `cf-optimistic-pulse`) on *both* sides before `Idiomorph.morph()` runs:
 *   - the live old subtree, walked with real DOM APIs, and
 *   - the incoming HTML string, rewritten with a small tag-attribute regex
 *     (it can't be walked with DOM APIs yet — Idiomorph itself parses it).
 *
 * These tests only verify that integration seam (consistent with this
 * repo's no-jsdom, hand-stub philosophy — see morph.test.mjs), not
 * idiomorph's own matching/reordering behaviour, which has its own upstream
 * test suite.
 */

import assert from 'node:assert/strict';
import { test } from 'node:test';

// --- Minimal DOM stubs (installed before importing the module) ------------
//
// Extends the `makeEl()` pattern from morph.test.mjs/optimistic.test.mjs
// with a tiny `[attr]`-selector-only `querySelectorAll` that actually walks
// a `_children` tree, since this feature needs real subtree traversal (the
// existing stub's `querySelectorAll()` always returns `[]`).

function matchesAttrSelector(el, selector) {
  const m = /^\[([\w-]+)\]$/.exec(selector);
  if (!m) return false;
  return el.getAttribute(m[1]) !== null;
}

function makeEl(dataset = {}, extra = {}) {
  const el = {
    dataset,
    id: extra.id ?? 'c1',
    tagName: extra.tagName ?? 'DIV',
    outerHTML: extra.outerHTML ?? '<div></div>',
    _attrs: { ...(extra.attrs || {}) },
    _children: extra.children || [],
    _replacedWith: null,
    setAttribute(k, v) {
      this._attrs[k] = String(v);
      if (k === 'id') this.id = String(v);
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
    matches(selector) {
      return matchesAttrSelector(this, selector);
    },
    querySelectorAll(selector) {
      const out = [];
      const walk = (node) => {
        for (const child of node._children) {
          if (matchesAttrSelector(child, selector)) out.push(child);
          walk(child);
        }
      };
      walk(this);
      return out;
    },
  };
  if (extra.id !== undefined || el._attrs.id === undefined) {
    if (el.id) el._attrs.id = el.id;
  }
  return el;
}

/**
 * A `[data-key]` list-item stub — no `_children` traversal needed for it.
 * Unlike `makeEl()`'s component-root default, this must NOT default to a
 * fake `id` of `'c1'`, since these tests are specifically about elements
 * that start out *without* a real id.
 */
function makeItem(key, { id } = {}) {
  const attrs = { 'data-key': key };
  if (id) attrs.id = id;
  return makeEl({}, { attrs, children: [], id: id ?? '' });
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

// --- Tests ------------------------------------------------------------------

test('_bridgeListKeys assigns a synthetic id to [data-key] elements in the incoming HTML that lack a real id', () => {
  const client = new ComponentClient();
  const el = makeEl({}, { children: [] }); // no live data-key descendants yet

  const html = '<div id="c1"><ul><li data-key="a">A</li><li data-key="b">B</li></ul></div>';
  const out = client._bridgeListKeys(el, html);

  assert.match(out, /<li id="cf-key-a" data-key="a">A<\/li>/);
  assert.match(out, /<li id="cf-key-b" data-key="b">B<\/li>/);
  // The root element already had a real id and must be left untouched.
  assert.match(out, /^<div id="c1">/);
});

test('_bridgeListKeys leaves [data-key] elements alone when they already carry a real id', () => {
  const client = new ComponentClient();
  const el = makeEl({}, { children: [] });

  const html = '<li id="custom-1" data-key="a">A</li>';
  const out = client._bridgeListKeys(el, html);

  assert.equal(out, html, 'element with an existing real id must not be rewritten');
});

test('_bridgeListKeys tags matching elements in the live old subtree in place', () => {
  const client = new ComponentClient();
  const itemA = makeItem('a');
  const itemB = makeItem('b', { id: 'already-real' });
  const root = makeEl({}, { children: [itemA, itemB] });

  client._bridgeListKeys(root, '');

  assert.equal(itemA.getAttribute('id'), 'cf-key-a', 'missing id should be synthesized from data-key');
  assert.equal(itemB.getAttribute('id'), 'already-real', 'existing real id must not be overridden');
});

test('_bridgeListKeys returns falsy/empty html unchanged', () => {
  const client = new ComponentClient();
  const el = makeEl({}, { children: [] });
  assert.equal(client._bridgeListKeys(el, ''), '');
});

test('update() bridges reordered [data-key] list items onto matching ids on both sides before morphing', () => {
  const client = new ComponentClient();
  const itemA = makeItem('a');
  const itemB = makeItem('b');
  const el = makeEl({ state: '{}' }, { id: 'c1', children: [itemA, itemB] });
  registry.c1 = el;

  // Incoming render reorders the list (b before a) and has no ids yet.
  const html = '<div id="c1"><ul><li data-key="b">B</li><li data-key="a">A</li></ul></div>';

  let morphArgs = null;
  const originalMorph = Idiomorph.morph;
  Idiomorph.morph = (...args) => {
    morphArgs = args;
  };
  try {
    client.update(el, html, '{}');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  assert.ok(morphArgs, 'Idiomorph.morph should have been called');
  // Incoming HTML handed to morph must carry synthesized ids for both items.
  assert.match(morphArgs[1], /<li id="cf-key-b" data-key="b">B<\/li>/);
  assert.match(morphArgs[1], /<li id="cf-key-a" data-key="a">A<\/li>/);
  // The live (old) subtree must carry the *same* synthesized ids, so
  // Idiomorph's id-based matching links each old node to its new
  // counterpart regardless of position.
  assert.equal(itemA.getAttribute('id'), 'cf-key-a');
  assert.equal(itemB.getAttribute('id'), 'cf-key-b');
  delete registry.c1;
});

test('update() with no [data-key] content passes the HTML through unchanged (no regression)', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' }, { children: [] });
  registry.c1 = el;

  let morphArgs = null;
  const originalMorph = Idiomorph.morph;
  Idiomorph.morph = (...args) => {
    morphArgs = args;
  };
  try {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  assert.equal(morphArgs[1], '<div id="c1">2</div>');
  delete registry.c1;
});

test('rollback() bridges [data-key] items in the snapshot HTML before morphing back', () => {
  const client = new ComponentClient();
  const itemA = makeItem('a');
  const el = makeEl(
    { state: '{"count":2}' },
    {
      id: 'c1',
      children: [itemA],
      outerHTML: '<div id="c1"><li data-key="a">A</li></div>',
    },
  );
  registry.c1 = el;

  client._snapshot(el, 'c1');

  let morphArgs = null;
  const originalMorph = Idiomorph.morph;
  Idiomorph.morph = (...args) => {
    morphArgs = args;
  };
  try {
    client.rollback('c1');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  assert.ok(morphArgs, 'Idiomorph.morph should have been called');
  assert.match(morphArgs[1], /<li id="cf-key-a" data-key="a">A<\/li>/);
  delete registry.c1;
});
