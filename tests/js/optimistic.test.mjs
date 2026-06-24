/**
 * Node-native tests for client-side optimistic UI wiring in component-client.js.
 *
 * Run with: node --test tests/js/
 *
 * These use lightweight DOM stubs (no jsdom dependency) to verify the three
 * behaviours that issue #16 requires:
 *   1. applyOptimistic merges state and sets CSS-hook attributes.
 *   2. _computeOptimistic reads declarative data-optimistic / -toggle markers.
 *   3. dispatch() applies the prediction *before* the fetch resolves, and
 *      reconciles (not rolls back) on success.
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
    setAttribute(k, v) {
      this._attrs[k] = v;
    },
    getAttribute(k) {
      return k in this._attrs ? this._attrs[k] : null;
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
  querySelector: () => null, // no csrf <meta>
  cookie: '',
  getElementById: (id) => registry[id] ?? null,
  addEventListener: () => {}, // swallow DOMContentLoaded
  createElement: () => makeEl({}),
};

const { ComponentClient } = await import(
  '../../src/component_framework/static/component_framework/js/component-client.js'
);

// --- Tests ----------------------------------------------------------------

test('applyOptimistic merges state and exposes CSS-hook attributes', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: JSON.stringify({ count: 1, interested: false }) });

  client.applyOptimistic(el, { count: 2, interested: true });

  assert.deepEqual(JSON.parse(el.dataset.state), { count: 2, interested: true });
  assert.equal(el.dataset.optimistic, 'true');
  assert.equal(el.getAttribute('data-optimistic-count'), '2');
  assert.equal(el.getAttribute('data-optimistic-interested'), 'true');
});

test('applyOptimistic skips object/null values for attribute hooks', () => {
  const client = new ComponentClient();
  const el = makeEl({ state: '{}' });

  client.applyOptimistic(el, { nested: { a: 1 }, missing: null, ok: 'yes' });

  assert.equal(el.getAttribute('data-optimistic-nested'), null);
  assert.equal(el.getAttribute('data-optimistic-missing'), null);
  assert.equal(el.getAttribute('data-optimistic-ok'), 'yes');
});

test('_computeOptimistic reads an explicit data-optimistic patch', () => {
  const client = new ComponentClient();
  const trigger = { dataset: { optimistic: '{"x": 1, "y": true}' } };

  assert.deepEqual(client._computeOptimistic(trigger, 'c1'), { x: 1, y: true });
});

test('_computeOptimistic toggles a boolean field for data-optimistic-toggle', () => {
  const client = new ComponentClient();
  registry.c1 = makeEl({ state: JSON.stringify({ interested: false }) });
  const trigger = { dataset: { optimisticToggle: 'interested' } };

  assert.deepEqual(client._computeOptimistic(trigger, 'c1'), { interested: true });
  delete registry.c1;
});

test('_computeOptimistic returns null when nothing is declared', () => {
  const client = new ComponentClient();
  assert.equal(client._computeOptimistic({ dataset: {} }, 'c1'), null);
});

test('dispatch applies the prediction before fetch resolves, reconciles on success', async () => {
  const client = new ComponentClient();
  const el = makeEl({ component: 'counter', state: JSON.stringify({ count: 1 }) });
  registry.c1 = el;

  let resolveFetch;
  globalThis.fetch = () => new Promise((r) => (resolveFetch = r));

  // Spy on reconciliation vs rollback.
  let updated = false;
  let rolledBack = false;
  client.update = () => {
    updated = true;
  };
  client.rollback = () => {
    rolledBack = true;
  };

  const p = client.dispatch('c1', 'increment', {}, { optimistic: { count: 2 } });

  // Synchronously (before the fetch resolves) the prediction is already applied.
  assert.equal(el.dataset.optimistic, 'true');
  assert.equal(JSON.parse(el.dataset.state).count, 2);
  assert.equal(el.dataset.loading, 'true');

  resolveFetch({
    ok: true,
    json: async () => ({ html: '<div id="c1">2</div>', state: '{"count":2}', component_id: 'c1' }),
  });
  await p;

  assert.equal(updated, true, 'server render should reconcile');
  assert.equal(rolledBack, false, 'no rollback on success');
  delete registry.c1;
});

test('dispatch rolls back when the request fails', async () => {
  const client = new ComponentClient();
  const el = makeEl({ component: 'counter', state: JSON.stringify({ count: 1 }) });
  registry.c1 = el;

  globalThis.fetch = async () => ({ ok: false, status: 500, text: async () => 'boom' });

  let rolledBack = false;
  client.rollback = () => {
    rolledBack = true;
  };

  await client.dispatch('c1', 'increment', {}, { optimistic: { count: 2 } });
  assert.equal(rolledBack, true, 'failed request should roll back the optimistic prediction');
  delete registry.c1;
});
