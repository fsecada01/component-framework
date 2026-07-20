/**
 * Node-native tests for the morph-based DOM reconciliation in
 * component-client.js (Epic B, B1 — #22).
 *
 * Run with: just test-js   (node's test runner over a tests/js glob)
 *
 * idiomorph itself ships its own upstream test suite; ours is a pinned,
 * unmodified vendor copy, so these tests only verify the *integration seam* —
 * that ComponentClient.update()/rollback() delegate to Idiomorph.morph()
 * instead of doing a full innerHTML replace — consistent with this repo's
 * existing no-jsdom, hand-stub test philosophy (see optimistic.test.mjs).
 */

import assert from 'node:assert/strict';
import { test } from 'node:test';

// --- Minimal DOM stubs (installed before importing the module) ------------

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

// --- Tests ------------------------------------------------------------------

test('update() delegates to Idiomorph.morph() instead of replaceWith', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' });
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

  assert.ok(morphArgs, 'Idiomorph.morph should have been called');
  assert.equal(morphArgs[0], el, 'morph should target the existing element in place');
  assert.equal(morphArgs[1], '<div id="c1">2</div>');
  assert.equal(morphArgs[2].morphStyle, 'outerHTML');
  assert.equal(el._replacedWith, null, 'element should not be swapped via replaceWith');
  delete registry.c1;
});

test('update() sets data-state and clears optimistic markers after morphing', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}', optimistic: 'true' });
  el.setAttribute('data-optimistic-count', '2');
  registry.c1 = el;

  const originalMorph = Idiomorph.morph;
  Idiomorph.morph = () => {};
  try {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  assert.equal(el.dataset.state, '{"count":2}');
  assert.equal(el.dataset.optimistic, undefined);
  delete registry.c1;
});

test('update() skips morph and clears optimistic markers when server returns empty HTML', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}', optimistic: 'true' });
  el.setAttribute('data-optimistic-count', '2');

  const originalMorph = Idiomorph.morph;
  let morphCalled = false;
  Idiomorph.morph = () => {
    morphCalled = true;
  };
  try {
    client.update(el, '');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  assert.equal(morphCalled, false, 'morph should not be called for empty HTML');
  assert.equal(el.dataset.optimistic, undefined);
  assert.equal(el.getAttribute('data-optimistic-count'), null);
});

test('rollback() delegates to Idiomorph.morph() with the snapshot HTML instead of replaceWith', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":2}' }, { outerHTML: '<div id="c1" data-state=\'{"count":1}\'>1</div>' });
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
  assert.equal(morphArgs[0], el, 'rollback should morph the existing element in place');
  assert.equal(morphArgs[1], '<div id="c1" data-state=\'{"count":1}\'>1</div>');
  assert.equal(morphArgs[2].morphStyle, 'outerHTML');
  assert.equal(el._replacedWith, null, 'element should not be swapped via replaceWith');
  delete registry.c1;
});

test('rollback() is a no-op when there is no snapshot', () => {
  const client = new ComponentClient();
  const el = makeEl({});
  registry.c1 = el;

  let morphCalled = false;
  const originalMorph = Idiomorph.morph;
  Idiomorph.morph = () => {
    morphCalled = true;
  };
  try {
    client.rollback('c1');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  assert.equal(morphCalled, false);
  delete registry.c1;
});
