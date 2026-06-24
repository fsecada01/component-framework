"""Minimal Flask example for the component framework.

Run::

    pip install "component-framework[flask]"
    python examples/flask_example.py
    # open http://localhost:5000

A server-rendered counter component. Clicking the buttons POSTs the event to
``/components/counter``; the bundled ``component-client.js`` swaps in the
authoritative server render.
"""

from flask import Flask, render_template_string
from jinja2 import DictLoader

from component_framework.adapters.flask import FlaskRenderer, register_component_routes
from component_framework.core.component import Component
from component_framework.core.registry import registry

app = Flask(__name__)

# Register a component template into the app's Jinja environment so the shared
# FlaskRenderer can resolve it (the renderer uses app.jinja_env).
app.jinja_env.loader = DictLoader(
    {
        "counter.html": (
            '<div id="{{ component_id }}" data-component="counter"'
            " data-state='{{ state | tojson }}' data-endpoint=\"/components/\">"
            "  <p>Count: {{ state.count }}</p>"
            '  <button data-event="increment" data-payload=\'{"amount": 1}\'>+</button>'
            '  <button data-event="decrement" data-payload=\'{"amount": 1}\'>-</button>'
            "</div>"
        )
    }
)

# Share the app's Jinja environment with the component renderer.
Component.renderer = FlaskRenderer(app)

# Wire POST /components/<name>.
register_component_routes(app)


@registry.register("counter")
class Counter(Component):
    """A simple counter with increment/decrement handlers."""

    template_name = "counter.html"

    def mount(self):
        super().mount()
        self.state["count"] = self.params.get("initial", 0)

    def on_increment(self, amount: int = 1):
        self.state["count"] = self.state.get("count", 0) + amount

    def on_decrement(self, amount: int = 1):
        self.state["count"] = self.state.get("count", 0) - amount


INDEX = """<!doctype html>
<html>
  <head><title>Flask + Component Framework</title></head>
  <body>
    <h1>Counter</h1>
    {{ counter_html | safe }}
    <script type="module">
      import { componentClient } from
        "https://cdn.jsdelivr.net/gh/fsecada01/component-framework/src/component_framework/static/component_framework/js/component-client.js";
      componentClient.bind();
    </script>
  </body>
</html>
"""


@app.route("/")
def index():
    """Render the page with an initial counter component."""
    counter = Counter(initial=0)
    result = counter.dispatch()  # mount + render
    return render_template_string(INDEX, counter_html=result["html"])


if __name__ == "__main__":
    app.run(debug=True, port=5000)
