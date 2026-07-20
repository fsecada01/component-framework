/**
 * Node-native tests for focus / in-flight-input / scroll preservation across
 * morph patches (Epic B, B2 — #22).
 *
 * Run with: node --test "tests/js/**\/*.test.mjs"
 * (`just test-js` has a pre-existing cmd.exe glob-expansion bug on Windows —
 * documented as out of scope in PR #43 — so invoke node directly.)
 *
 * Split into two concerns, tested at two different levels, matching this
 * repo's no-jsdom, hand-stub philosophy (see morph.test.mjs's header):
 *
 *   1. Focus / in-flight input value: idiomorph itself already implements
 *      this (restoreFocus defaults to true; ignoreActiveValue protects the
 *      focused element's value). We can't exercise idiomorph's internal
 *      browser-API-dependent logic (document.activeElement,
 *      HTMLInputElement, etc.) without jsdom, so — like morph.test.mjs —
 *      these tests only verify the *integration seam*: that
 *      update()/rollback() actually pass `ignoreActiveValue: true` in the
 *      config handed to Idiomorph.morph(). Without that flag (confirmed by
 *      reading vendor/idiomorph.js's ignoreAttribute()/syncInputValue()
 *      logic around line 751-761 and 834-846), idiomorph overwrites a
 *      focused input's `value` with the server's render even though
 *      restoreFocus keeps the element focused — i.e. focus survives by
 *      default, but the user's in-flight keystrokes don't, unless this flag
 *      is set.
 *
 *   2. Scroll position: idiomorph has no concept of scroll at all (pure DOM
 *      patching), so this is bespoke bookkeeping this repo owns outright,
 *      not idiomorph configuration. These tests exercise the real capture/
 *      restore logic end to end against hand-rolled DOM stubs.
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
    scrollTop: extra.scrollTop ?? 0,
    scrollLeft: extra.scrollLeft ?? 0,
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
    querySelector() {
      return null;
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

// --- Focus / in-flight input value (integration seam) ----------------------

test('update() passes ignoreActiveValue: true so a focused input\'s in-flight text is not clobbered', () => {
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
  assert.equal(
    morphArgs[2].ignoreActiveValue,
    true,
    'update() must protect the focused element\'s value across the morph',
  );
  delete registry.c1;
});

test('rollback() passes ignoreActiveValue: true so a focused input\'s in-flight text is not clobbered', () => {
  const client = new ComponentClient();
  const el = makeEl(
    { state: '{"count":2}' },
    { outerHTML: '<div id="c1" data-state=\'{"count":1}\'>1</div>' },
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
  assert.equal(
    morphArgs[2].ignoreActiveValue,
    true,
    'rollback() must protect the focused element\'s value across the morph',
  );
  delete registry.c1;
});

// --- Scroll position (bespoke, not idiomorph) -------------------------------

test('update() restores the root element\'s own scroll offsets when the morph resets them', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' }, { scrollTop: 120, scrollLeft: 30 });
  registry.c1 = el;

  const originalMorph = Idiomorph.morph;
  Idiomorph.morph = () => {
    // Simulate idiomorph patching the element in a way that resets scroll.
    el.scrollTop = 0;
    el.scrollLeft = 0;
  };
  try {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  assert.equal(el.scrollTop, 120);
  assert.equal(el.scrollLeft, 30);
  delete registry.c1;
});

test('update() restores a scrollable descendant\'s scroll offset even when idiomorph recreates that node', () => {
  const client = new ComponentClient();

  const oldList = makeEl({}, { id: 'msg-list', tagName: 'DIV', scrollTop: 250 });
  const newList = makeEl({}, { id: 'msg-list', tagName: 'DIV', scrollTop: 0 });

  const el = makeEl({ state: '{"count":1}' });
  el.querySelectorAll = (selector) => (selector === '[id]' ? [oldList] : []);
  el.querySelector = (selector) => (selector === '[id="msg-list"]' ? newList : null);
  registry.c1 = el;

  const originalMorph = Idiomorph.morph;
  // Idiomorph is stubbed out entirely here; `newList` already stands in for
  // whatever node idiomorph would have produced, wired up via the
  // querySelector stub above so restore can re-locate it by id.
  Idiomorph.morph = () => {};
  try {
    client.update(el, '<div id="c1"><div id="msg-list"></div></div>', '{"count":2}');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  assert.equal(newList.scrollTop, 250, 'recreated descendant should have its scroll offset restored');
  assert.equal(oldList.scrollTop, 250, 'captured snapshot should reflect the pre-morph offset');
  delete registry.c1;
});

test('update() does not restore scroll for a descendant with no id (cannot be re-located, mirrors idiomorph\'s own restoreFocus limitation)', () => {
  const client = new ComponentClient();

  // No `id` set -> selector '[id]' would not match this in a real DOM; the
  // stub simulates that filtering by only returning matches for '[id]'.
  const noIdDescendant = makeEl({}, { id: '', tagName: 'DIV', scrollTop: 80 });

  const el = makeEl({ state: '{"count":1}' });
  el.querySelectorAll = () => [];
  registry.c1 = el;

  const originalMorph = Idiomorph.morph;
  Idiomorph.morph = () => {
    noIdDescendant.scrollTop = 0;
  };
  try {
    client.update(el, '<div id="c1"><div></div></div>', '{"count":2}');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  // Nothing should have thrown, and there is no mechanism to restore an
  // unidentified node's scroll position -- documented limitation.
  assert.equal(noIdDescendant.scrollTop, 0);
  delete registry.c1;
});

test('update() does not capture or restore scroll when nothing is scrolled (no-op fast path)', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{"count":1}' });
  registry.c1 = el;

  const originalMorph = Idiomorph.morph;
  let morphCalled = false;
  Idiomorph.morph = () => {
    morphCalled = true;
  };
  try {
    client.update(el, '<div id="c1">2</div>', '{"count":2}');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  assert.equal(morphCalled, true);
  assert.equal(el.scrollTop, 0);
  assert.equal(el.scrollLeft, 0);
  delete registry.c1;
});

test('rollback() restores the root element\'s own scroll offsets when the morph resets them', () => {
  const client = new ComponentClient();
  const el = makeEl(
    { state: '{"count":2}' },
    { outerHTML: '<div id="c1" data-state=\'{"count":1}\'>1</div>', scrollTop: 60 },
  );
  registry.c1 = el;
  client._snapshot(el, 'c1');

  const originalMorph = Idiomorph.morph;
  Idiomorph.morph = () => {
    el.scrollTop = 0;
  };
  try {
    client.rollback('c1');
  } finally {
    Idiomorph.morph = originalMorph;
  }

  assert.equal(el.scrollTop, 60);
  delete registry.c1;
});

test('_captureScrollPositions ignores elements with zero scroll offsets', () => {
  const client = new ComponentClient();
  const el = makeEl({}, { scrollTop: 0, scrollLeft: 0 });

  const positions = client._captureScrollPositions(el);

  assert.deepEqual(positions, []);
});

test('_captureScrollPositions records the root plus any scrolled descendants with an id', () => {
  const client = new ComponentClient();
  const descendant = makeEl({}, { id: 'panel', scrollTop: 40, scrollLeft: 5 });
  const el = makeEl({}, { scrollTop: 100, scrollLeft: 0 });
  el.querySelectorAll = (selector) => (selector === '[id]' ? [descendant] : []);

  const positions = client._captureScrollPositions(el);

  assert.equal(positions.length, 2);
  assert.ok(positions.some((p) => p.isRoot && p.top === 100 && p.left === 0));
  assert.ok(positions.some((p) => !p.isRoot && p.id === 'panel' && p.top === 40 && p.left === 5));
});
