# E-Commerce Live View

> **No React. No Redux. No build step.**
> A real-time product page and shopping cart built entirely with server-side
> components, HTMX, and WebSocket — all in plain Python.

This example walks through a production-grade e-commerce storefront that
renders product details and manages a shopping cart in real-time. Along the
way it demonstrates every major feature introduced in the Beta milestone:
optimistic UI, composition, caching, rate limiting, and permission-gated
endpoints.

---

## The Scenario

A fashion retailer wants:

- A **product page** that loads instantly and reflects live inventory
- A **shopping cart** that updates the moment you click *Add to Cart* —
  with no full-page reload, no spinner, and no client-side state management
- A **size selector** that shows stock levels in real-time
- A **checkout button** that is gated behind authentication

The standard answer in 2024 is: _"Build it in React, manage state with Redux
(or Zustand, or Jotai...), wire up API routes, keep client and server state
in sync, handle loading states, write hydration logic, set up a bundler..."_

The **component-framework answer** is: write Python.

---

## Architecture at a Glance

```
Browser (HTMX + component-client.js)
  │  POST /components/product/  (event, state, payload)
  │  POST /components/cart/
  │  WS   /ws/components/
  ▼
Django Views (django_views.py)
  │  Permission check → rate-limit check → dispatch
  ▼
ProductComponent / CartComponent  (pure Python)
  │  mount() / hydrate() → handle_event() → render()
  ▼
Django Template Engine (Jinja2 / Django templates)
```

**Key insight:** state lives on the server. The browser sends events and
receives rendered HTML + a serialised state blob. There is no client-side
state machine — the server *is* the source of truth.

---

## Compare: React vs Component Framework

| Concern | React + Redux | Component Framework |
|---|---|---|
| State location | Client bundle | Server (Python dict) |
| Sync strategy | REST/GraphQL polling or WS events | Built-in server state |
| Optimistic UI | `useOptimistic()` + rollback logic | `get_optimistic_patch()` hook |
| Auth gating | Middleware + `useSession()` hook | `permission_classes = [IsAuthenticated]` |
| Rate limiting | Custom middleware or API gateway | `@rate_limit_component("10/minute")` |
| Caching | `useMemo` + server-side cache | `class CachedProductView(CacheMixin, ComponentView)` |
| Composition | JSX slots + prop drilling | `fill_slot()` / `render_slots()` |
| Build step | webpack/Vite required | **None** |
| JS payload | 150–400 KB (gzipped) | ~5 KB (`htmx.min.js` + `component-client.js`) |
| DX feedback | TypeScript + ESLint + Storybook | Pure Python + ruff + pytest |

---

## Project Setup

```bash
pip install component-framework django django-channels
```

```python
# settings.py
INSTALLED_APPS = [
    ...,
    "channels",
    "component_framework",
]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
    }
}
```

---

## 1. ProductComponent

The product component renders a product card — image, name, price, stock
level, size selector — and handles size selection and add-to-cart events.

### The Component

```python
# shop/components.py
from component_framework.core import Component, registry
from component_framework.core.permissions import IsAuthenticated
from component_framework.adapters.django_ratelimit import rate_limit_component

from .models import Product, Inventory


@registry.register("product")
class ProductComponent(Component):
    """
    Renders a single product with real-time inventory and size selection.

    params:
        product_id (int): The product to display.
        user       (User | AnonymousUser): Injected by the view.
    """

    template_name = "shop/product.html"
    slots = ["reviews", "recommendations"]

    def mount(self):
        product_id = self.params["product_id"]
        product = Product.objects.select_related("brand").get(pk=product_id)
        inventory = Inventory.objects.filter(product=product).values(
            "size", "stock"
        )

        self.state.update({
            "id": product.pk,
            "name": product.name,
            "brand": product.brand.name,
            "price": str(product.price),
            "description": product.description,
            "image_url": product.main_image.url,
            "sizes": [
                {"size": row["size"], "stock": row["stock"]}
                for row in inventory
            ],
            "selected_size": None,
            "in_cart": False,
        })

    def on_select_size(self, size: str):
        """User clicked a size option."""
        self.state["selected_size"] = size

    def on_add_to_cart(self):
        """Add selected size to cart. Requires a size to be selected."""
        if not self.state.get("selected_size"):
            self.errors["size"] = "Please select a size first."
            return

        # Notify the cart component via WebSocket broadcast
        from component_framework.core import ws_manager
        import asyncio

        user_id = self.params.get("user_id")
        if user_id:
            asyncio.create_task(
                ws_manager.broadcast(
                    group=f"cart-{user_id}",
                    message={
                        "event": "add_item",
                        "payload": {
                            "product_id": self.state["id"],
                            "size": self.state["selected_size"],
                        },
                    },
                )
            )

        self.state["in_cart"] = True

    # ── Optimistic UI ────────────────────────────────────────────────────
    def get_optimistic_patch(self, event: str, payload: dict) -> dict | None:
        """
        Return immediate state updates the client can apply before the server
        responds. On error, the client rolls back to pre-patch state.
        """
        if event == "select_size":
            # Show selection immediately — no spinner needed.
            return {"selected_size": payload.get("size")}

        if event == "add_to_cart":
            # Disable the button immediately to prevent double-clicks.
            return {"in_cart": True}

        return None
```

### The View

```python
# shop/views.py
from component_framework.adapters.django_views import AuthenticatedComponentView
from component_framework.adapters.django_ratelimit import RateLimitMixin


class ProductComponentView(RateLimitMixin, AuthenticatedComponentView):
    """
    Rate-limited, authenticated component endpoint.

    - Unauthenticated requests → JSON 401 (HTMX handles the redirect)
    - More than 30 requests / minute per user → JSON 429 + Retry-After
    """

    throttle_rate = "30/minute"

    def get_throttle_key(self, request, **kwargs):
        return f"product:{request.user.pk}"

    def get_component_params(self, request, **kwargs):
        params = super().get_component_params(request, **kwargs)
        params["product_id"] = int(kwargs.get("product_id", 0))
        return params
```

### URL Configuration

```python
# shop/urls.py
from django.urls import path
from .views import ProductComponentView

urlpatterns = [
    path(
        "components/product/<int:product_id>/",
        ProductComponentView.as_view(),
        name="product_component",
    ),
]
```

### The Template

```html
{# shop/templates/shop/product.html #}
<div id="product-{{ component_id }}"
     hx-target="this"
     hx-swap="outerHTML">

  <img src="{{ state.image_url }}" alt="{{ state.name }}" />

  <div class="product-info">
    <p class="brand">{{ state.brand }}</p>
    <h1>{{ state.name }}</h1>
    <p class="price">${{ state.price }}</p>
    <p>{{ state.description }}</p>
  </div>

  {# Size Selector #}
  <div class="sizes">
    {% for option in state.sizes %}
      <button
        hx-post="{% url 'product_component' state.id %}"
        hx-vals='{"event": "select_size", "size": "{{ option.size }}"}'
        class="size-btn {% if state.selected_size == option.size %}selected{% endif %}"
        {% if option.stock == 0 %}disabled{% endif %}>
        {{ option.size }}
        {% if option.stock < 5 %}
          <span class="low-stock">Only {{ option.stock }} left</span>
        {% endif %}
      </button>
    {% endfor %}
  </div>

  {% if errors.size %}
    <p class="error">{{ errors.size }}</p>
  {% endif %}

  {# Slot: reviews injected by parent page view #}
  {% if slots.reviews %}
    <section class="reviews">{{ slots.reviews|safe }}</section>
  {% endif %}

  {# Add to Cart #}
  <button
    hx-post="{% url 'product_component' state.id %}"
    hx-vals='{"event": "add_to_cart"}'
    {% if state.in_cart or not state.selected_size %}disabled{% endif %}>
    {% if state.in_cart %}Added to Cart ✓{% else %}Add to Cart{% endif %}
  </button>
</div>
```

---

## 2. CartComponent

The cart component renders the current cart contents, handles quantity
changes and item removal, and updates in real-time via WebSocket push.

### The Component

```python
@registry.register("cart")
class CartComponent(Component):
    """
    Shopping cart — persists in server state, updates via WebSocket events.

    State shape:
        items: list[{product_id, name, size, price, qty}]
        total: str (Decimal as string for JSON safety)
    """

    template_name = "shop/cart.html"

    def mount(self):
        self.state.update({"items": [], "total": "0.00"})

    def _recalculate_total(self):
        from decimal import Decimal
        total = sum(
            Decimal(item["price"]) * item["qty"]
            for item in self.state["items"]
        )
        self.state["total"] = str(total)

    def on_add_item(self, product_id: int, size: str):
        """Add an item or increment its quantity."""
        from .models import Product

        for item in self.state["items"]:
            if item["product_id"] == product_id and item["size"] == size:
                item["qty"] += 1
                self._recalculate_total()
                return

        product = Product.objects.get(pk=product_id)
        self.state["items"].append({
            "product_id": product_id,
            "name": product.name,
            "size": size,
            "price": str(product.price),
            "qty": 1,
            "image_url": product.thumbnail.url,
        })
        self._recalculate_total()

    def on_remove_item(self, product_id: int, size: str):
        self.state["items"] = [
            item for item in self.state["items"]
            if not (item["product_id"] == product_id and item["size"] == size)
        ]
        self._recalculate_total()

    def on_set_qty(self, product_id: int, size: str, qty: int):
        if qty <= 0:
            self.on_remove_item(product_id, size)
            return
        for item in self.state["items"]:
            if item["product_id"] == product_id and item["size"] == size:
                item["qty"] = qty
        self._recalculate_total()

    # ── Optimistic UI ────────────────────────────────────────────────────
    def get_optimistic_patch(self, event: str, payload: dict) -> dict | None:
        if event == "remove_item":
            # Immediately hide the row before the server confirms deletion.
            product_id = payload.get("product_id")
            size = payload.get("size")
            remaining = [
                item for item in self.state.get("items", [])
                if not (item["product_id"] == product_id and item["size"] == size)
            ]
            return {"items": remaining}
        return None
```

### Real-Time WebSocket Updates

When `ProductComponent.on_add_to_cart()` fires, it broadcasts a message to
the user's cart channel. The cart component listens via the WebSocket manager
and pushes an updated render to the browser — all without the user doing
anything.

```python
# shop/consumers.py  (Django Channels)
from component_framework.core import ws_manager

class CartConsumer(ws_manager.ComponentConsumer):
    """
    WebSocket consumer that keeps the cart widget live.

    The parent class handles:
      - group subscription (based on user id)
      - dispatching incoming messages as component events
      - pushing rendered HTML back to the client
    """
    component_name = "cart"

    async def websocket_connect(self, message):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return
        await self.channel_layer.group_add(
            f"cart-{user.pk}", self.channel_name
        )
        await super().websocket_connect(message)
```

### Caching the Cart Page (not the cart itself)

The cart *widget* must never be cached (it's user-specific and mutable).
But the **product listing page** that surrounds it is a great caching target:

```python
class CachedProductPageView(CacheMixin, ComponentView):
    """
    Cache the product page HTML for 5 minutes per product.
    Event requests (add_to_cart, select_size) bypass the cache automatically.
    """

    cache_timeout = 300

    def get_cache_key(self, name, params, state):
        product_id = params.get("product_id", "unknown")
        return f"product-page:{product_id}"
```

---

## 3. Page Composition

The full product page composes `ProductComponent` with a `ReviewsComponent`
injected into the `"reviews"` slot:

```python
# shop/page_views.py
from django.views.generic import TemplateView
from component_framework.core import compose, registry


class ProductPageView(TemplateView):
    template_name = "shop/product_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product_id = self.kwargs["product_id"]

        reviews_cls = registry.get("reviews")
        product_cls = registry.get("product")

        # compose() wires the slot and renders both components in one call
        product = compose(
            product_cls,
            params={"product_id": product_id, "user": self.request.user},
            reviews=reviews_cls(product_id=product_id),
        )
        result = product.dispatch()
        context["product_html"] = result["html"]
        context["product_state"] = result["state"]
        return context
```

```html
{# shop/templates/shop/product_page.html #}
{% extends "base.html" %}
{% block content %}
  <div class="product-layout">
    <div class="product-main">
      {{ product_html|safe }}
    </div>
    <aside class="cart-sidebar">
      {# Cart synced via WebSocket — initial HTML rendered server-side #}
      <div id="cart-widget"
           hx-ext="ws"
           ws-connect="/ws/cart/">
        {# Initial cart HTML injected here by CartPageView #}
      </div>
    </aside>
  </div>
{% endblock %}
```

---

## 4. Permission Gating

The checkout component requires authentication. Using `IsAuthenticated` on
the component class means *any* view that serves it — FBV or CBV — enforces
the permission automatically:

```python
from component_framework.core.permissions import IsAuthenticated

@registry.register("checkout")
class CheckoutComponent(Component):
    permission_classes = [IsAuthenticated]
    template_name = "shop/checkout.html"

    def mount(self):
        user = self.params["user"]
        self.state["email"] = user.email
        self.state["address"] = user.profile.shipping_address

    def on_place_order(self, payment_token: str):
        # ... process payment, create Order record ...
        self.state["confirmed"] = True
```

An unauthenticated HTMX request to `POST /components/checkout/` receives:

```json
{"error": "Authentication required"}
```

with HTTP `401`. HTMX's `htmx:responseError` event handles the redirect to
the login page on the client side.

---

## 5. Rate Limiting the Cart

Protect `add_to_cart` from accidental double-submission or abuse:

```python
from component_framework.adapters.django_ratelimit import rate_limit_component

urlpatterns = [
    path(
        "components/cart/",
        rate_limit_component("5/second")(
            AuthenticatedComponentView.as_view()
        ),
    ),
]
```

Or via `RateLimitMixin` on the class:

```python
class CartView(RateLimitMixin, AuthenticatedComponentView):
    throttle_rate = "5/second"

    def get_throttle_key(self, request, **kwargs):
        return f"cart:{request.user.pk}"
```

Excess requests receive `HTTP 429` with a `Retry-After` header. The JS
client handles this gracefully and rolls back any optimistic state.

---

## Why Not React?

Here is the same cart update in a React + Redux stack vs component-framework:

### React approach

```typescript
// 1. Action creator
const addToCart = createAsyncThunk('cart/addItem', async (item, { dispatch }) => {
  const response = await fetch('/api/cart/', {
    method: 'POST',
    body: JSON.stringify(item),
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
  });
  if (!response.ok) throw new Error('Failed to add item');
  return response.json();
});

// 2. Reducer
const cartSlice = createSlice({
  name: 'cart',
  initialState: { items: [], total: '0.00', status: 'idle' },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(addToCart.pending,   (state) => { state.status = 'loading'; })
      .addCase(addToCart.fulfilled, (state, action) => {
        state.items = action.payload.items;
        state.total = action.payload.total;
        state.status = 'idle';
      })
      .addCase(addToCart.rejected,  (state) => { state.status = 'error'; });
  },
});

// 3. Optimistic update (useOptimistic in React 19)
function CartButton({ item }) {
  const [optimisticItems, addOptimistic] = useOptimistic(
    items,
    (state, newItem) => [...state, { ...newItem, pending: true }]
  );
  return (
    <button onClick={async () => {
      addOptimistic(item);            // immediate UI update
      await dispatch(addToCart(item)); // server round-trip
    }}>
      Add to Cart
    </button>
  );
}
```

**That's three separate concepts** (async thunk, reducer, optimistic hook)
across multiple files, plus TypeScript types, plus a store provider, plus
serialisation/deserialisation.

### Component Framework approach

```python
@registry.register("cart")
class CartComponent(Component):

    def on_add_item(self, product_id: int, size: str):
        ...  # 10 lines of plain Python, see above

    def get_optimistic_patch(self, event: str, payload: dict) -> dict | None:
        if event == "add_item":
            return {"items": self.state["items"] + [{**payload, "qty": 1}]}
        return None
```

One class. One language. One `pytest` test suite.

---

## Testing

Because components are pure Python, the full cart behaviour is testable
without Django, HTMX, or a running server:

```python
from component_framework.testing import ComponentTestCase, MockRenderer
from shop.components import CartComponent

class TestCartComponent(ComponentTestCase):

    def setUp(self):
        CartComponent.renderer = MockRenderer()

    def test_add_item(self):
        cart = self.make_component(CartComponent)
        cart.mount()
        cart.on_add_item(product_id=42, size="M")

        self.assertEqual(len(cart.state["items"]), 1)
        self.assertEqual(cart.state["items"][0]["qty"], 1)

    def test_add_same_item_increments_qty(self):
        cart = self.make_component(CartComponent)
        cart.mount()
        cart.on_add_item(product_id=42, size="M")
        cart.on_add_item(product_id=42, size="M")

        self.assertEqual(len(cart.state["items"]), 1)
        self.assertEqual(cart.state["items"][0]["qty"], 2)

    def test_remove_item(self):
        cart = self.make_component(CartComponent)
        cart.mount()
        cart.on_add_item(product_id=42, size="M")
        cart.on_remove_item(product_id=42, size="M")

        self.assertEqual(cart.state["items"], [])

    def test_optimistic_patch_remove(self):
        cart = self.make_component(CartComponent)
        cart.mount()
        cart.on_add_item(product_id=42, size="M")

        patch = cart.get_optimistic_patch("remove_item", {"product_id": 42, "size": "M"})
        self.assertEqual(patch["items"], [])

    def test_total_recalculates(self):
        cart = self.make_component(CartComponent)
        cart.mount()
        cart.state["items"] = [{"product_id": 1, "size": "S", "price": "29.99", "qty": 3}]
        cart._recalculate_total()

        self.assertEqual(cart.state["total"], "89.97")
```

Run the suite:

```bash
pytest shop/tests/ -v
```

---

## Running the Example

```bash
# 1. Clone and install
git clone https://github.com/fsecada01/component-framework
cd component-framework/examples/django_example
uv sync

# 2. Migrate and seed
python manage.py migrate
python manage.py loaddata shop_fixtures.json

# 3. Start Redis (for WebSocket channel layer)
docker run -p 6379:6379 redis:7-alpine

# 4. Run
python manage.py runserver
```

Open `http://localhost:8000/shop/product/1/` — add items to the cart and
watch the cart widget update in real-time via WebSocket, with optimistic
UI making every click feel instant.

---

## Summary

| Feature | Component | How |
|---|---|---|
| Real-time render | `ProductComponent` | HTMX `hx-post` + server re-render |
| Optimistic UI | `get_optimistic_patch()` | Pre-dispatch state patch → JS rollback on error |
| WebSocket push | `CartComponent` | `ws_manager.broadcast()` → Channels → browser |
| Auth gating | `CheckoutComponent` | `permission_classes = [IsAuthenticated]` |
| Rate limiting | Cart endpoint | `RateLimitMixin` / `@rate_limit_component` |
| Page caching | Product page | `CacheMixin` (event requests bypass) |
| Composition | `ProductPageView` | `compose(product, reviews=reviews_instance)` |
| Testing | All components | Pure Python — `pytest`, `MockRenderer`, `ComponentTestCase` |
