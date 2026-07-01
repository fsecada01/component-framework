# CSRF & Cross-Site WebSocket Hijacking — Coverage & Integration Guide

**Scope:** HTTP mutation surfaces (`POST /components/{name}`, `.../stream`) and WebSocket handlers across the FastAPI, Litestar, Flask, and Django adapters.
**Audit date:** 2026-07-01 · **Branch state:** audited read-only against `master` (Issue #21 / A4).
**Verdict in one line:** CSRF is enforced **only** on the Django adapter, and only when the host app keeps `CsrfViewMiddleware` enabled and avoids the shipped `csrf_exempt` variants. FastAPI, Litestar, and Flask adapters have **zero** CSRF enforcement. All WebSocket handlers accept connections with no origin check or handshake token (CSWSH-exposed).

---

## 1. Threat model & exploitability framing (read this first)

CSRF only matters when the endpoint authenticates the caller via **ambient credentials** — a session cookie the browser attaches automatically. The component endpoints are **unauthenticated by default** (`permission_classes` defaults to `[AllowAny]`, and the non-Django adapters have no auth hook at all). Two consequences:

- **Default deployment (no auth):** the endpoints are already world-writable; there is no privileged session to ride, so "CSRF" is academic — the real exposure is the missing auth, not the missing token.
- **The dangerous configuration** is the *natural next step* an integrator takes: bolt cookie/session auth onto these routes (Django login, `AuthenticatedComponentView`, a FastAPI/Litestar/Flask session cookie) **without** adding CSRF. At that point every mutation endpoint is CSRF-exploitable on the three non-Django adapters.

**Aggravating factor — form-encoded bodies are accepted.** Every HTTP adapter's `_parse_request_data` falls back to `application/x-www-form-urlencoded` when the content-type isn't JSON (`fastapi.py:48-52`, `litestar.py:48-52`, `flask.py:81-86`, `django_views.py:57-63`). That means an attacker does **not** need `fetch`/CORS/preflight — a plain auto-submitting cross-origin `<form>` reaches the handler and mutates state. This is the classic, no-JS-required CSRF vector, and it is wide open on FastAPI/Litestar/Flask the moment cookie auth exists.

**The client is not the mitigation.** `component-client.js` reads a Django CSRF token (`readCsrfToken()`, lines 54-64) and sends `X-CSRFToken` (lines 189-193). That header is *only* meaningful to Django; nothing on the FastAPI/Litestar/Flask side reads or validates it. It is also trivially bypassed — an attacker writes their own request and simply omits the header.

---

## 2. Per-adapter coverage table

| Adapter | CSRF enforcement today | Gap | Recommended integration | Exploitable in default deploy? |
|---|---|---|---|---|
| **FastAPI** (`adapters/fastapi.py`) | **None.** Routes added via `add_api_route(..., methods=["POST"])` (lines 170-181). No dependency, no token check. FastAPI ships no built-in CSRF. | Full CSRF gap. Accepts form-encoded bodies → plain cross-origin form works. | Document + optionally wire `fastapi-csrf-protect` (double-submit cookie) as an opt-in `Depends`; or instruct integrators to enforce CSRF at a middleware/proxy layer. Provide a hook so the token is verified before `async_dispatch`. | Only if the app adds cookie/session auth. No auth by default → CSRF moot but endpoint is unauthenticated-open. |
| **Litestar** (`adapters/litestar.py`) | **None.** `@post` handlers (lines 79, 119). No `csrf_config` referenced or required. | Full CSRF gap. Litestar has a **built-in `CSRFConfig`** that the adapter neither wires nor documents. | Document that integrators pass `csrf_config=CSRFConfig(secret=...)` to the `Litestar(...)` app; verify our handlers honor the `_csrf_token` field / `x-csrftoken` header Litestar expects. Lowest-effort real fix of the three — the framework already has the machinery. | Same as FastAPI: only under cookie/session auth. |
| **Flask** (`adapters/flask.py`) | **None.** Blueprint `POST /<name>` (lines 174-183). Flask ships no built-in CSRF. | Full CSRF gap. `strict_slashes=False` widens the match surface but is not itself the risk. | Document Flask-WTF `CSRFProtect` or Flask-SeaSurf; provide guidance to `csrf.protect()` the blueprint or exempt-and-re-protect. Consider an opt-in decorator in the adapter. | Same: only under cookie/session auth. Flask's newest adapter, least battle-tested. |
| **Django (FBV `component_view`)** (`adapters/django_views.py:25-116`) | **Yes, by inheritance.** Not `csrf_exempt`; Django's `CsrfViewMiddleware` enforces the token when the middleware is in `MIDDLEWARE`. Header name `X-CSRFToken` matches Django's default `CSRF_HEADER_NAME`, and `component-client.js` sends exactly that. | Coverage is **conditional**, not intrinsic: breaks if the host removes the middleware, and the package *ships* bypasses (`component_view_no_csrf` line 116; `CSRFExemptComponentView` line 361). No `ensure_csrf_cookie` is provided by the framework — the host page must set the cookie, else the JS finds no token. | Keep the non-exempt view as the documented default. Doc note: enable `CsrfViewMiddleware`, ensure the CSRF cookie is set on the host page, avoid the exempt variants unless an alternative protection exists. | Not exploitable in a standard Django deploy (middleware on). Exploitable only via `component_view_no_csrf` / `CSRFExemptComponentView`, or disabled middleware (as `examples/django_example` does "for demo"). |
| **Django (CBV `ComponentView` + subclasses)** | **Yes, same basis** as FBV (not exempt). `AuthenticatedComponentView` (line 312) adds cookie/session auth — so here CSRF actually *matters* and Django's middleware covers it. | `CSRFExemptComponentView` (line 361) is an explicit, documented opt-out that removes protection from an authenticated surface. | Same as FBV. Strengthen the docstring/doc warning on the exempt view: only for APIs using token/bearer auth, never for cookie-session flows. | Not by default; exploitable only via the exempt subclass. |

---

## 3. WebSocket CSRF / CSWSH limitation

All four WS paths accept the socket **immediately and unconditionally**:

- `core/websocket.py` — transport-agnostic `ComponentWebSocketManager.handle_message` dispatches `component_event` with no auth/origin concept (lines 77-154).
- `adapters/fastapi_websocket.py:52` — `await websocket.accept()` then loop. No origin check, no token at handshake.
- `adapters/litestar_websocket.py:55` — same pattern.
- `adapters/django_websocket.py:62` — `await self.accept()` in `ComponentConsumer.connect()`. Django's `CsrfViewMiddleware` does **not** run on Channels.

**Limitation to document:** there is no origin validation and no handshake token on any adapter. Browsers do **not** enforce same-origin on WebSocket handshakes, and they **do** attach cookies to cross-origin WS requests. Any WS handler that trusts an ambient session is exposed to **Cross-Site WebSocket Hijacking (CSWSH)** — a malicious page can open a socket as the victim and drive `component_event` mutations.

**Guidance:**
- **Django Channels:** wrap the consumer in `AllowedHostsOriginValidator` (or `OriginValidator`) in `asgi.py`/routing. Document as required for authenticated WS.
- **FastAPI / Litestar:** validate the `Origin` header against an allowlist before `accept()`, and/or require a token (query-param or first-message token minted from the authenticated HTTP session) at handshake.
- Until an origin check exists, do not rely on cookie/session identity inside WS handlers.

---

## 4. Documentation reality-check

- **CLAUDE.md** claims "CSRF protection required for mutations" — **aspirational, not implemented** for 3 of 4 HTTP adapters; reword to state only Django enforces it and the others require host-level integration.
- **README.md** is accurate: roadmap line 597 "CSRF coverage for FastAPI / Litestar / Flask HTTP paths (today Django-only)"; line 655 "CSRF handling for WebSockets is manual." A4 lands under 0.6.0b.
- **docs/examples/wizard.md:26-27** concedes "the FastAPI adapter has no CSRF" — consistent.
- **examples/django_example** disables CSRF ("for demo purposes," README line 231; `urls_cbv.py` wires `CSRFExemptComponentView`) — models the insecure pattern; add a pointer to production guidance.
- This document is the canonical CSRF/CSWSH reference for the project.

---

## 5. Prioritized follow-up work (issues to be opened)

1. **P1 — `docs: add SECURITY_CSRF.md with per-adapter CSRF/CSWSH guidance`** — land this report as canonical docs; correct CLAUDE.md wording.
2. **P1 — `feat(litestar): document + wire built-in CSRFConfig for component routes`** — highest value-to-effort; framework already has the machinery. Add integration test.
3. **P1 — `feat(websocket): add Origin validation to FastAPI/Litestar WS handshake + document Channels OriginValidator`** — closes the CSWSH gap.
4. **P2 — `docs+feat(fastapi): CSRF integration guide (fastapi-csrf-protect) + optional verify hook`**
5. **P2 — `docs+feat(flask): CSRF integration (Flask-WTF/SeaSurf) for component blueprint`**
6. **P2 — `security: strengthen warnings on Django csrf_exempt variants`** — permit only for non-cookie auth; consider runtime warning.
7. **P3 — `security: reject/normalize form-encoded bodies where JSON is expected`** — form-encoding enables no-preflight cross-origin CSRF; evaluate requiring JSON for the JS client path. Cross-refs roadmap "Cross-adapter request-parse hardening" (README:599).

**Related, kept separate:** unsigned client-round-tripped state (A1/HMAC work) is a distinct integrity gap — CSRF protects *who* can trigger a mutation; state signing protects *what* state they can forge.
