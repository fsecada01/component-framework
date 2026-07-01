# Research Report — Production-Grade Python LiveView: Market Analysis & Differentiation

**Date:** 2026-06-24
**Subject library:** `component-framework` (framework-agnostic Python server components; FastAPI / Django / Litestar / Flask adapters; HTMX, server-owned state, Pydantic forms, WebSocket + SSE, optimistic UI, permissions, composition)
**Depth:** Deep (3 parallel research streams, web-sourced, 2024–2026 data)
**Scope note:** This is a research report only. Recommendations are for human decision; no code was changed.

---

## Executive Summary

1. **The market wind is at our back.** Among Django developers, HTMX adoption grew **5%→24% (2021→2025)** and Alpine.js **3%→14%**, while React (37%→32%) and Vue (28%→17%) declined. JetBrains/DSF call it a "pendulum shift back to server-side templates." Django 6.0 shipped official template partials, institutionally blessing the HTMX workflow. FastAPI rose to 38% of Python web devs. (JetBrains State of Django 2025; Python Developers Survey 2024.)

2. **There is a real, specific vacuum.** Elixir has Phoenix LiveView, Laravel has Livewire, Rails has Hotwire — each a single "blessed" answer. **Python has fragmentation:** 15+ LiveView-workalike libraries, and the leaders are nearly all **Django-only** (django-unicorn 2.6k★, tetra 611★) with "unknown" production maturity. **No mature server-component library exists for FastAPI or Litestar.**

3. **Our positioning occupies genuine whitespace.** No competitor is simultaneously (a) framework-agnostic across FastAPI **and** Django **and** Litestar **and** Flask, (b) HTML-template + HTMX based (not a Python-widget DSL, not a React compiler), (c) LiveView-style server-owned state, (d) batteries-included (Pydantic forms + WS + SSE + optimistic UI + permissions + composition). Every close competitor gives up at least two of these.

4. **But "production-grade" has a high bar we only partly meet.** Against the Phoenix LiveView / Livewire / Hotwire reference set, we have the foundational layer (state lifecycle, size guard, forms, WS/SSE, optimistic UI, permissions, testing) but are **missing or unverified** on several table-stakes items — most notably **signed/tamper-proof state**, **live SPA navigation**, **file uploads with progress**, **focus/scroll-preserving DOM morphing with stable keys**, **reconnection state-resync**, and **observability**. See the gap analysis (§4).

5. **Recommended wedge:** "**The production-grade server-component library for the apps you already have — across FastAPI, Django, Litestar, and Flask.**" Compete as a *library, not a platform* (the funded players — Reflex, Posit/Shiny, Pydantic/FastUI — all push standalone/cloud, vacating the embeddable-library niche). Lead with the FastAPI/Litestar communities that have **no** server-component option today.

---

## 1. Market Trend (Confidence: High)

The shift toward hypermedia / "HTML over the wire" in Python is evidenced across the largest survey datasets:

| Frontend tech (Django devs) | 2021 | 2025 | Direction |
|---|---|---|---|
| HTMX | 5% | **24%** | ⬆ ~5× |
| Alpine.js | 3% | **14%** | ⬆ ~4.5× |
| React | 37% | 32% | ⬇ |
| Vue | 28% | 17% | ⬇ |

- **Django 6.0** ships official template partials — core support for the HTMX/Alpine pattern. (JetBrains State of Django 2025.)
- **Python Developers Survey 2024** (PSF+JetBrains, 30k+): web use 46%; **FastAPI 29%→38%**; HTML/CSS +15%, JS +14% among web devs — consistent with more server-rendered work.
- **State of JS 2025**: htmx remains "most admired"; React satisfaction at a low despite ~84% usage (JS-community survey → lower confidence for a Python read, but corroborating).

**Verdict:** The hypermedia movement is real, fast-growing, and now endorsed inside Django itself.

---

## 2. Competitive Landscape (Confidence: High on metrics — live GitHub API, 2026-06-24)

### 2.1 Master table

| Library | Stars | Last push | Paradigm | Target framework(s) | Realtime | Backing |
|---|---|---|---|---|---|---|
| **Reflex** (ex-Pynecone) | 28.6k | 2026-06-24 | Python→React compiler (full-stack) | Standalone | WS built-in | VC ($5M seed, YC W23, Lux) |
| **NiceGUI** | 15.9k | 2026-06-23 | Server-side Python widgets (Vue/Quasar) | Standalone (on FastAPI) | Socket.IO | Zauberzeug |
| **FastUI** | 9.0k | 2026-04-01 | JSON-schema → prebuilt React | FastAPI | No | Pydantic — **inactive/on-hold** |
| **ReactPy** (ex-iDOM) | 8.1k | 2026-04-18 | Server VDOM-in-Python over WS | **Agnostic** (Django/FastAPI/Flask/Starlette) | WS | Community; slowing |
| **H2O Wave** | 4.2k | 2026-06-11 | Server push via Go relay | Standalone | WS | H2O.ai (data/AI) |
| **Rio** | 3.4k | 2026-06-22 | Server-side reactive Python (no HTML/JS) | Standalone | WS | rio.dev startup |
| **Django Unicorn** | 2.7k | 2026-05-22 | Livewire-style reactive components | **Django only** | AJAX (no WS) | Community |
| **Solara** | 2.2k | 2026-06-22 | React-style reactive, ipywidgets/web | Standalone/Jupyter | WS | Widgetti |
| **django-htmx** | 2.0k | 2026-06-14 | htmx helper utils (the baseline) | **Django** | none by default | Adam Johnson |
| **Shiny for Python** | 1.7k | 2026-06-11 | Reactive graph, server-rendered | Standalone | WS | **Posit** (commercial) |
| **JustPy** | 1.3k | 2026-01-06 | Server-side Python (Vue/Quasar) | Standalone | WS | **Sunset** (→NiceGUI) |
| **Tetra** | 611 | 2026-03-27 | LiveView/Livewire-style, colocated, Alpine | **Django only** | AJAX (no native WS) | Community |
| **django-sockpuppet** | 446 | 2023-01-07 | StimulusReflex port, DOM morph over WS | **Django only** | WS | **Abandoned** |
| **PyView** | 137 | 2026-06-20 | **Direct Phoenix LiveView port** | Standalone (Starlette) | WS (LV protocol) | Early-stage |
| *(data-app category)* Streamlit 45k / Gradio 43k / Dash 24k | — | — | script-rerun / callback dashboards | standalone/Flask | WS | Snowflake / HF / Plotly |

### 2.2 Paradigm classification (the strategic cut)

- **A. LiveView-style (server-owned state, server-rendered HTML, thin JS)** — our family: **PyView** (purest port, but standalone + LV-client JS, tiny, no batteries), **Tetra** (Django+Alpine, no WS/SSE), **Django Unicorn** (Django, AJAX), **Sockpuppet** (dead).
- **B. Server-side Python-UI (widgets are Python objects, no HTML authoring):** NiceGUI, Rio, JustPy, H2O Wave, Solara — adjacent intent, different DX/audience (internal tools).
- **C. Python→JS compiler / full-stack:** Reflex — *is* the framework, not an adapter.
- **D. JSON-UI schema-driven:** FastUI — not LiveView, and inactive.
- **E. Server-VDOM-in-Python:** ReactPy — the *other* framework-agnostic player, but a React/VDOM mental model, not HTML+HTMX+server-state.
- **F. Data-app adjacent (not general LiveView):** Streamlit / Gradio / Dash / Shiny — dominate by stars but solve dashboards/ML demos, not general apps with auth/forms/composition.

### 2.3 Overlap with `component-framework` (ranked by collision)

1. **Tetra** — highest *paradigm* overlap, but **Django-locked, Alpine, no WS/SSE, no Pydantic forms**. Our agnostic + WS/SSE + Pydantic + permissions story is a clean differentiator.
2. **Django Unicorn** — same niche, larger mindshare, but **AJAX-only, Django-only**, no composition/permissions framework.
3. **PyView** — closest LiveView fidelity, but **standalone/Starlette-only, immature, ships LV's JS** (not HTMX), no batteries.
4. **ReactPy** — the other agnostic option, but React/VDOM, not HTML/HTMX/server-state. Different audience.
5. **Reflex / NiceGUI / Rio** — overlap on "server state + realtime" but they **replace your view layer** (own DSL / own framework); not a drop-in adapter.

**Whitespace we occupy:** framework-agnostic across all four major Python web frameworks **+** HTML/HTMX **+** server-owned state **+** batteries-included. No competitor matches more than ~three of those four.

---

## 3. Demand & "Vacuum" Thesis (Confidence: Medium-High)

- **Every competitor frames itself against LiveView/Livewire** — that framing only sells to an audience that wants it (Tetra, Unicorn, Django LiveView, Reactor, PyView all say so explicitly).
- A cross-language **`liveviews/liveviews` catalog lists 15+ Python entries** — sustained community pull.
- **FastHTML's launch** (Answer.AI / Jeremy Howard, Aug 2024) articulated "a big gap … around a highly scalable, web-foundation-based, pure-Python framework" — a high-credibility demand statement; top HN item.
- **Pain points cited:** SPA over-engineering ("React is overkill"), client-state failure modes (stale cache, optimistic-rollback bugs, races, subscription leaks), backend/frontend context-switching.

**Vacuum verdict:** The opening is real and *specific* — a **blessed, consolidated, cross-framework, production-grade** server-component library. It is **not** an empty field (the gap is crowded with Django-only and immature projects), so differentiation must be sharp. The single strongest pillar: **there is no mature server-component option for FastAPI/Litestar today.**

⚠️ *Lower-confidence caveat:* survey data suggests developers **rarely switch frameworks mid-project**, so the naive "portability" pitch is weak. Reframe the agnostic value as **(a)** library/skill reuse for consultants & multi-service shops, **(b)** reaching FastAPI/Litestar communities with no option today, **(c)** one mental model across a polyglot Python org — *addressable-market expansion, not migration.*

---

## 4. Production-Readiness Gap Analysis

Below: the production-grade checklist synthesized from Phoenix LiveView (gold standard), Livewire, and Hotwire — each item tagged **table-stakes (TS)** vs **differentiator (D)** — mapped to `component-framework`'s current state per its docs (`✅ have` / `🟡 partial-or-unverified` / `❌ missing`). Items marked 🟡/❌ that are TS are the priority gaps.

> **Architectural note:** CPython has no BEAM-style cheap stateful process, so the natural fit is the **Livewire/Hotwire stateless model** (signed state in the browser, re-rendered per request, scales without sticky sessions) over LiveView's stateful per-connection model. `component-framework` already hedges this way (server-owned state + size guard + SSE + HTTP-first HTMX). That makes a few "stateful-only" differentiators (presence, per-connection inspector) lower priority, and a few stateless essentials (**signed state**, **morphing**, **navigation**) higher priority.

### 4.1 State management
| Item | Tier | Status | Note |
|---|---|---|---|
| Server-owned, JSON-serializable state + lifecycle | TS | ✅ | mount→hydrate→handle_event→render→dehydrate |
| Two-pass render (full HTML first load → diff connected) | TS | 🟡 | verify disconnected/connected render parity |
| Hydrate/dehydrate with type reconstruction | TS | ✅ | Pydantic-backed |
| State size guard | TS | ✅ | 64 KB warn / 512 KB hard |
| **Signed/validated state (HMAC; client can't tamper)** | **TS** | **❌** | **Key gap.** State is round-tripped to the client; Livewire signs its snapshot (checksum → corruption exception). "Don't trust client" is documented but no signing primitive is. **Security-relevant — top priority.** |
| State recovery on reconnect (re-run mount) | TS | 🟡 | verify resync after WS drop |
| Ephemeral/streamed state for large collections | D | ❌ | LiveView streams/`temporary_assigns` (infinite scroll) |
| Locked/immutable server-trusted props | D | 🟡 | permissions exist; no `#[Locked]`-style field guard |
| Computed/memoized non-persisted state | D | ❌ | — |
| Distributed state across nodes (Redis) | TS-if-stateful | 🟡 | Django Channels + Redis layer documented; not unified cross-adapter |

### 4.2 Realtime transport
| Item | Tier | Status | Note |
|---|---|---|---|
| Primary transport + reconnection + resync | TS | 🟡 | WS present (FastAPI/Django/Litestar); resync unverified |
| HTTP request-per-action path (no socket needed) | TS | ✅ | HTMX HTTP-first |
| SSE one-way fallback | D | ✅ | `StreamingComponent` |
| WS scaling via Redis pub/sub | TS-multinode | 🟡 | Django path documented; FastAPI/Litestar fan-out not unified |
| Sticky-session requirement documented | TS-if-stateful | 🟡 | document explicitly |
| Backpressure handling | D | ❌ | — |
| Multi-user presence | D | ❌ | hardest to replicate outside BEAM; low priority given stateless lean |
| Model-driven broadcasting | D | 🟡 | WS broadcast exists; no `Broadcastable`-style sugar |
| **Flask WS/SSE** | TS-parity | ❌ | Flask adapter is HTTP-only (known) |

### 4.3 DOM updates
| Item | Tier | Status | Note |
|---|---|---|---|
| DOM morphing (patch changed nodes, not innerHTML swap) | TS | 🟡 | verify whether client uses morph (idiomorph/morphdom) vs full swap |
| Preserve focus/scroll/in-flight input during patch | TS | 🟡 | depends on morph strategy |
| Stable list reconciliation key | TS | 🟡 | confirm a `wire:key`/`:key` equivalent |
| **Server-side change tracking (statics once, dynamics diffed)** | D | ❌ | LiveView's core moat; very high effort — *likely out of scope* |
| Targeted update strategies (append/prepend/replace/remove) | TS | 🟡 | confirm coverage |
| JS-owned "don't morph" escape hatch | TS | 🟡 | confirm `phx-update=ignore` equivalent |

### 4.4 Navigation
| Item | Tier | Status | Note |
|---|---|---|---|
| **SPA-style navigation + history (pushState)** | **TS** | **❌** | No first-class live navigation (relies on htmx-boost at best). Significant gap for "real apps." |
| In-place param update vs full navigate | D | ❌ | — |
| Loading indicator/progress on slow nav | TS | 🟡 | optimistic loading hooks exist; no nav progress bar |
| Scroll preservation/restoration | TS | ❌ | — |
| Prefetch-on-hover / `@persist` / active-link | D | ❌ | — |

### 4.5 Forms
| Item | Tier | Status | Note |
|---|---|---|---|
| Change/submit bindings + server validation + error display | TS | ✅ | Pydantic forms |
| Real-time / on-blur validation | TS | 🟡 | confirm partial-validation path |
| Debounce/throttle on input | TS | 🟡 | available via htmx; confirm defaults |
| 422 re-render convention for failed submits | TS | 🟡 | **verify adapters return non-2xx correctly** (common footgun) |
| Form-state recovery after reconnect | D | ❌ | LiveView `phx-auto-recover` |
| Submit-button disable/busy during in-flight | TS | 🟡 | optimistic UI partially covers |
| **File uploads: progress, multiple, constraints** | **TS** | **❌** | Major gap; expected in production apps |
| Drag-drop / direct-to-S3 uploads | D | ❌ | — |
| Dirty-state indicator | D | ❌ | — |

### 4.6 Performance
| Item | Tier | Status | Note |
|---|---|---|---|
| Minimal payloads (diff/deferred) | TS | 🟡 | full-HTML responses today; no diff |
| Request batching | D | ❌ | — |
| Bounded per-connection memory | TS-if-stateful | 🟡 | size guard helps |
| Lazy/deferred component loading | D | ❌ | — |
| **Published benchmarks** | D | ❌ | **No framework publishes cross-framework numbers — credibility opportunity** (already on our 1.0 roadmap) |

### 4.7 Security
| Item | Tier | Status | Note |
|---|---|---|---|
| CSRF on mutations | TS | 🟡 | Django ✅; **no automatic CSRF for WS (known); confirm FastAPI/Litestar/Flask HTTP CSRF guidance** |
| **Signed/validated state (tamper-proof)** | TS | ❌ | see §4.1 — top gap |
| Never trust client state; authz per action | TS | ✅ | permissions + per-event checks |
| Auth-boundary primitive (`live_session`/`on_mount`) | D | 🟡 | permission classes; no session-group boundary |
| Signed, authz-gated realtime subscriptions | D | ❌ | even Hotwire's signed streams never expire — room to beat |
| Rate limiting | TS | ✅ | `RateLimitMixin` |
| XSS-safe escaping by default | TS | ✅ | template-engine default |

### 4.8 Developer experience
| Item | Tier | Status | Note |
|---|---|---|---|
| In-process, browser-free testing | TS | ✅ | `ComponentTestCase` — strong selling point |
| State/render/event/error assertions | TS | 🟡 | confirm full matcher set |
| JS interop hooks w/ lifecycle | TS | 🟡 | confirm `phx-hook` equivalent + re-attach after swap |
| Declarative optimistic JS commands | D | 🟡 | optimistic UI exists; no `JS.show/hide/toggle` DSL |
| Latency simulation for dev | D | ❌ | rare; cheap differentiator |
| Type safety on public/event APIs | D | ✅ | Pydantic + `ty` |
| Loading-state CSS classes auto-applied | TS | ✅ | `[data-loading]`/`[data-optimistic]` (shipped 0.5.0b0) |
| **Devtools / inspector** | D | ❌ | on 1.0 roadmap |
| Comprehensive docs/tutorials | TS | 🟡 | API ref + guides; **no narrative user guide** (1.0 roadmap) |

### 4.9 Operations
| Item | Tier | Status | Note |
|---|---|---|---|
| Telemetry/observability (lifecycle spans + timing) | TS | ❌ | logging only; no metrics/spans |
| Horizontal scaling story (stateless OR sticky+Redis) | TS | 🟡 | document the stateless model explicitly |
| Graceful degradation w/o JS / w/o live connection | TS | 🟡 | HTMX HTTP path helps; document |
| Offline detection / visibility-throttled polling | D | ❌ | `wire:offline` / `wire:poll.visible` |
| Deployment guide (ASGI workers, LB, WS termination) | TS | 🟡 | partial |
| Live process/memory inspector | D | ❌ | ties to devtools |

---

## 5. Competitor Weaknesses to Exploit (Confidence: Medium-High)

- **Reflex** ($5M seed): compiles to a Next.js SPA with a **mandatory live WS to Python** (scaling/latency), steep learning curve, **standalone (can't drop into an existing app)**, dashboard-leaning, Pydantic-v1 internals → **Python 3.14 build failures** (#5964).
- **Django Unicorn / Tetra / Reactor / Sockpuppet** — **Django-only**; several require Channels/Redis; small bus factors; "unknown" production maturity.
- **FastUI** — Pydantic-backed but **officially dormant** (#368) — a *funded project that stalled*, leaving the segment open.
- **ReactPy** — every interaction is a server round-trip + VDOM diff → less responsive than client React.
- **Streamlit / Dash / Shiny** — **not for general apps**; rerun/callback models hit a ceiling as apps grow.

---

## 6. Differentiation Strategy (recommendation — for human decision)

**Positioning line:** *"Production-grade server components for the app you already have — across FastAPI, Django, Litestar, and Flask. Write HTML, keep your framework, skip the SPA."*

Defensible wedges (ranked):

1. **Cross-framework reach** — the only library spanning FastAPI + Django + Litestar + Flask. Lead with **FastAPI/Litestar**, which have *no* server-component option. (Frame as market expansion, not migration.)
2. **htmx-native, not WS-mandatory** — HTTP-first with optional SSE/WS sidesteps the channel-layer ops burden and rides the htmx wave (24% and climbing).
3. **Real apps, not dashboards** — explicitly counter-position vs Streamlit/Dash/Shiny/Reflex: CRUD, auth-gated flows, forms, SEO-able pages.
4. **Drop-in / progressive enhancement** — add reactive components to an existing app; no rebuild (unlike Reflex).
5. **Production-grade & maintained** — permissions, CSRF, rate-limit, size guards, caching, browser-free testing — in a segment littered with abandoned/immature projects, *stability is itself a differentiator*.
6. **Library, not platform** — no lock-in, no mandatory cloud. The funded players' commercial incentives push them to standalone/cloud, *vacating* the embeddable-library niche.

**Credibility must-haves to earn the "production-grade" claim** (close these before marketing it hard): **signed/tamper-proof state**, **live navigation**, **file uploads w/ progress**, **focus/scroll-preserving morph + stable keys**, **reconnection resync**, **observability**, and **published benchmarks**.

---

## 7. Suggested Roadmap Sequencing (recommendation only)

- **Tier 0 — Credibility/security (do first):** signed/validated state (HMAC); verify DOM morph + stable keys + focus/scroll preservation; confirm 422 re-render convention; document the stateless-scaling + sticky-session story.
- **Tier 1 — Table-stakes app features:** live SPA navigation (history, loading bar, scroll restore); file uploads with progress/constraints; reconnection state-resync; Flask WS/SSE parity; cross-adapter parse hardening (from the prior review).
- **Tier 2 — Win mindshare:** published benchmarks; devtools/inspector; telemetry/observability; latency simulation; declarative optimistic-JS command DSL; offline/visibility-aware polling.
- **Tier 3 — Advanced/optional:** ephemeral streams for large lists; presence (only if a stateful-WS mode is pursued); direct-to-S3 uploads; request batching/lazy components.
- **Cross-cutting:** the **API freeze + narrative user guide** (already on the 1.0 roadmap) gate a credible 1.0 tag.

---

## 8. Confidence & Open Questions

- **High:** market trend (multi-source surveys); competitor metrics (live GitHub API 2026-06-24); FastUI inactive; JustPy/Sockpuppet sunset.
- **Medium:** exact "developers asking for this" quotes (HN/Reddit bodies poorly indexed; HN returned HTTP 429); the framework-agnostic value thesis (devs rarely switch frameworks — needs user validation with consultants/multi-service shops).
- **To verify against our own source (the 🟡 rows in §4 are inferred from project docs, not a code read):** morph strategy, list keys, 422 handling, reconnection resync, partial-validation, CSRF coverage per adapter. **Recommend a follow-up `/sc:analyze` pass over the repo** to convert §4's 🟡 rows into confirmed have/missing.
- **Watch:** **PyView** (only pure LiveView port — nearest future competitor if it matures) and **FastHTML** (highest-credibility entrant; risk to "general pure-Python hypermedia" — track whether it stays standalone, leaving the embeddable niche open).

---

## Sources

**Surveys / trend:** JetBrains State of Django 2025 (https://blog.jetbrains.com/pycharm/2025/10/the-state-of-django-2025/) · Django Developers Survey 2025 (https://lp.jetbrains.com/django-developer-survey-2025/) · Python Developers Survey 2024 (https://lp.jetbrains.com/python-developers-survey-2024/)

**Demand / fragmentation:** liveviews catalog (https://github.com/liveviews/liveviews) · Django Packages live-views grid (https://djangopackages.org/grids/g/live-views/) · FastHTML launch (https://www.answer.ai/posts/2024-08-03-fasthtml.html)

**Competitors:** Reflex (https://github.com/reflex-dev/reflex · seed: https://reflex.dev/blog/seed-annoucement/ · Py3.14 issue: https://github.com/reflex-dev/reflex/issues/5964) · NiceGUI (https://github.com/zauberzeug/nicegui) · FastUI inactive (https://github.com/pydantic/FastUI/issues/368) · ReactPy (https://github.com/reactive-python/reactpy) · Rio (https://github.com/rio-labs/rio) · Django Unicorn (https://github.com/django-commons/django-unicorn) · Shiny for Python (https://github.com/posit-dev/py-shiny) · django-htmx (https://github.com/adamchainz/django-htmx) · JustPy (https://justpy.io/) · Tetra (https://www.tetraframework.com/) · django-sockpuppet (https://github.com/jonathan-s/django-sockpuppet) · PyView (https://github.com/ogrodnek/pyview)

**Production references:** Phoenix LiveView docs (https://phoenix-live-view.hexdocs.pm/Phoenix.LiveView.html · dom-patching · assigns-eex · live-navigation · uploads · external-uploads · form-bindings · security-model · LiveViewTest · telemetry · Presence: https://hexdocs.pm/phoenix/presence.html) · Laravel Livewire docs (https://livewire.laravel.com/docs/ — hydration, properties, validation, uploads, wire-navigate, wire-poll, wire-loading, security, testing, morphing) · Hotwire (https://turbo.hotwired.dev/handbook/ — drive, frames, streams, page_refreshes · Stimulus: https://stimulus.hotwired.dev/ · turbo-rails: https://github.com/hotwired/turbo-rails · Hotwire Native: https://native.hotwired.dev/)

**Scaling/transport:** LiveView scaling (https://honesw.com/blog/optimizing-phoenix-liveview-for-larger-scale-apps) · Redis pub/sub (https://medium.com/@hexshift/phoenix-and-redis-harnessing-transient-state-and-blazing-fast-pub-sub-051f3d3e97f8) · WS backpressure (https://hexshift.medium.com/websocket-backpressure-in-phoenix-liveview-how-to-handle-the-load-without-dropping-the-ball-bc16b058e7dd) · SSE vs WS (https://dev.to/alex_aslam/server-sent-events-vs-websockets-when-to-ditch-hotwire-55jb) · Action Cable security gap (https://github.com/hotwired/turbo-rails/issues/61)

*Star counts and push dates retrieved via GitHub API on 2026-06-24; treat as point-in-time.*
