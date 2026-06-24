# Development Plan — Path to Production-Grade 1.0

**Date:** 2026-06-24
**Source:** `claudedocs/research_liveview_market_2026-06-24.md` (Tier 0–3 gap analysis)
**Current version:** 0.5.0b0 · **Target:** 1.0.0 (stable, "production-grade" claim earned)

## Legend
- **Effort:** S = ~1–2 d · M = ~3–5 d · L = ~1–2 wk · XL = multi-week
- **Type:** TS = table-stakes (required to claim production-grade) · D = differentiator · ENABLER = unblocks others
- **Status today:** ❌ missing · 🟡 partial/unverified (per project docs; confirm in spike E0)

---

## Milestone map

| Milestone | Theme | Gate it unlocks |
|---|---|---|
| **0.6.0b** — Hardening Foundation | Tier 0: security, rendering fidelity, verification | Trust the state; trust the DOM patch |
| **0.7.0b** — Real-App Features | Tier 1: navigation, uploads, forms, realtime robustness | "Build a real app" credibility |
| **0.8.0b** — Mindshare | Tier 2: observability, benchmarks, DX | Public "production-grade" claim + marketing |
| **1.0.0** — Stable | API freeze, user guide, deploy guide, devtools | Frozen API + docs = 1.0 |
| **post-1.0** | Tier 3 advanced (streams, presence, S3, batching) | Opportunistic |

---

## Epics & work breakdown

### EPIC A — State Security & Integrity  *(→ 0.6.0b)*
The #1 credibility/security gap: server state round-trips to the client unsigned.

| ID | Task | Type | Effort | Depends |
|---|---|---|---|---|
| A1 | **Sign serialized state (HMAC)** with a configurable secret; verify on inbound, reject tampered (`CorruptStateError`) | TS / ENABLER | M | — |
| A2 | Key management + rotation story; doc "set `SECRET`/`STATE_SIGNING_KEY` per adapter" | TS | S | A1 |
| A3 | `Locked`/immutable server-trusted fields (client can't mutate) | D | S | A1 |
| A4 | Audit CSRF coverage across FastAPI / Litestar / Flask HTTP paths; document per-adapter; note WS CSRF limitation | TS | S | — |

### EPIC B — DOM Morphing & Rendering Fidelity  *(→ 0.6.0b)*
Foundation for navigation, forms, and optimistic UI quality.

| ID | Task | Type | Effort | Depends |
|---|---|---|---|---|
| B1 | **Adopt a morph swap** (idiomorph/morphdom) in `component-client.js` instead of innerHTML replace | TS / ENABLER | M | — |
| B2 | Preserve focus / scroll / in-flight input values across patches | TS | S | B1 |
| B3 | Stable list reconciliation key (`cf-key` / `data-key`) | TS | S | B1 |
| B4 | "Don't morph this" escape hatch (JS-owned regions) | TS | S | B1 |
| B5 | *(Spike)* Server-side change tracking (statics-once/dynamics-diff) — feasibility only; likely post-1.0 | D | M | B1 |

### EPIC C — Live Navigation  *(→ 0.7.0b)*
| ID | Task | Type | Effort | Depends |
|---|---|---|---|---|
| C1 | **SPA-style navigation** (intercept links/forms, swap, `pushState` history/back) | TS | L | B1 |
| C2 | Loading indicator / progress bar on slow navigations | TS | S | C1 |
| C3 | Scroll preservation/restoration across navigations | TS | S | C1 |
| C4 | In-place param update vs full navigate distinction | D | S | C1 |
| C5 | Prefetch-on-hover / persist-element / active-link | D | M | C1 |

### EPIC D — Forms & Uploads  *(→ 0.7.0b)*
| ID | Task | Type | Effort | Depends |
|---|---|---|---|---|
| D1 | **File uploads**: progress events, multiple files, size/type constraints, validation | TS | L | — |
| D2 | On-blur / real-time partial validation without full submit | TS | M | — |
| D3 | Debounce/throttle defaults on input bindings | TS | S | — |
| D4 | Verify + enforce **422 re-render** convention across adapters | TS | S | E0 |
| D5 | Submit-button disable/busy during in-flight | TS | S | B1 |
| D6 | Form-state recovery after reconnect (`auto-recover`) | D | M | F1 |
| D7 | Dirty-state indicator; drag-drop / direct-to-S3 upload | D | M | D1 |

### EPIC E — Realtime Robustness & Scaling  *(→ 0.7.0b)*
| ID | Task | Type | Effort | Depends |
|---|---|---|---|---|
| E0 | **Verification spike**: confirm the 🟡 rows (morph today, list keys, 422, reconnection, CSRF, partial-validation) via `/sc:analyze` over the repo | ENABLER | S | — |
| F1 | Reconnection + automatic state-resync after WS drop | TS | M | A1 |
| E2 | Unify WS fan-out via Redis pub/sub across adapters (not just Django) | TS-multinode | L | — |
| E3 | **Flask WS/SSE parity** (Flask adapter is HTTP-only today) | TS-parity | M | — |
| E4 | Cross-adapter request-parse hardening (`TypeError`→400, empty-state) — from prior review | TS | S | — |
| E5 | Document stateless scaling model + sticky-session guidance | TS | S | — |
| E6 | Multi-user presence (only if a stateful-WS mode is pursued) | D | XL | E2 |

### EPIC F — Observability & Performance  *(→ 0.8.0b)*
| ID | Task | Type | Effort | Depends |
|---|---|---|---|---|
| G1 | Telemetry: lifecycle spans (mount/handle_event/render) + timing hooks | TS | M | — |
| G2 | **Published benchmarks** (latency, payload, mem/connection, concurrency) | D | M | G1 |
| G3 | Lazy/deferred component loading (viewport / post-paint) | D | M | C1 |
| G4 | Request batching | D | M | — |

### EPIC G — Developer Experience  *(→ 0.8.0b / 1.0.0)*
| ID | Task | Type | Effort | Depends |
|---|---|---|---|---|
| H1 | Declarative optimistic-JS command DSL (show/hide/toggle/transition) | D | M | B1 |
| H2 | JS interop hooks w/ lifecycle + auto-reattach after swap | TS | M | B1 |
| H3 | Latency simulation for dev | D | S | — |
| H4 | **Devtools / inspector** (state/events/connections) | D | L | G1 |
| H5 | Offline detection + visibility-throttled polling | D | M | — |

### EPIC H — 1.0 Readiness  *(→ 1.0.0)*
| ID | Task | Type | Effort | Depends |
|---|---|---|---|---|
| I1 | **Freeze & document the public API** (mark provisional vs stable) | TS / GATE | M | most epics |
| I2 | Narrative user guide + tutorials | TS | L | — |
| I3 | Deployment guide (ASGI workers, LB, WS termination, sticky sessions) | TS | M | E5 |
| I4 | Graceful-degradation (no-JS / no-connection) documentation + tests | TS | S | — |

---

## Sequencing (dependency-ordered)

```
0.6.0b  ── E0 (spike) ─┬─ A1 → A2,A3        (sign state)
                       ├─ A4               (CSRF audit)
                       └─ B1 → B2,B3,B4    (morph foundation)   ▲ ENABLERS for everything below
                          E4               (parse hardening)

0.7.0b  ── C1 → C2,C3,C4,C5               (navigation; needs B1)
           D1 → D7 ; D2 ; D3 ; D4 ; D5    (forms & uploads)
           F1 (reconnect; needs A1) → D6
           E2 ; E3 ; E5                    (scaling, Flask parity, docs)

0.8.0b  ── G1 → G2 ; G3 (needs C1) ; G4   (observability/perf)
           H1,H2 (need B1) ; H3 ; H5      (DX)

1.0.0   ── I1 (API freeze; after epics) ; I2 ; I3 (needs E5) ; I4 ; H4 (devtools)

post-1.0 ─ B5 (server diff) ; E6 (presence) ; D7 S3 ; G4 batching   (advanced/optional)
```

## Critical path
**E0 → A1 + B1** are the gating enablers. A1 (signed state) is the security gate; B1 (morph) unblocks navigation, forms fidelity, optimistic-JS, and JS hooks. Land both early in 0.6.0b.

## Rough effort roll-up (planning only, not a commitment)
- 0.6.0b: ~3–4 wk (1 dev) — A1–A4, B1–B4, E0, E4
- 0.7.0b: ~5–7 wk — C1–C3, D1–D5, F1, E2/E3/E5
- 0.8.0b: ~4–5 wk — G1–G2, H1–H3, H5
- 1.0.0: ~4–5 wk — I1–I4, H4
- **Total to 1.0:** ~16–21 wk solo; compressible with parallelism (forms ‖ navigation ‖ observability are independent once B1 lands).

## Out-of-scope for 1.0 (explicit)
Server-side change-tracked diffing (B5), CRDT presence (E6), direct-to-S3 (D7 part), request batching (G4). Documented as post-1.0 so the milestone stays achievable.

## Proposed GitHub structure
- **Milestones:** `0.6.0b — Hardening`, `0.7.0b — Real-App Features`, `0.8.0b — Mindshare`, `1.0.0 — Stable`.
- **Issues:** one per task ID above (~40), labeled `epic:<A–H>`, `tier:table-stakes|differentiator`, `enhancement`/`security`/`docs`. Each epic also gets a tracking issue listing its task IDs.
