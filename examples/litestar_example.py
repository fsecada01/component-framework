"""Litestar example application with Counter component."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from litestar import Litestar, get
from litestar.response import Response

from component_framework.adapters.litestar import component_endpoint
from component_framework.components.counter import Counter
from component_framework.core import Component, Renderer


class Jinja2Renderer(Renderer):
    """Simple Jinja2 renderer for the example."""

    def __init__(self, templates_dir: Path):
        from jinja2 import Environment, FileSystemLoader

        self.env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)

    def render(self, template_name: str, context: dict) -> str:
        template = self.env.get_template(template_name)
        return template.render(**context)


# Configure renderer globally for all components
templates_dir = Path(__file__).parent.parent / "templates" / "components"
renderer = Jinja2Renderer(templates_dir)
Component.renderer = renderer


@get("/")
async def index() -> Response:
    """Serve demo page."""
    counter = Counter(initial=0)
    result = counter.dispatch()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Component Framework Demo (Litestar)</title>
        <script src="https://unpkg.com/htmx.org@1.9.10"></script>
        <style>
            body {{
                font-family: system-ui, -apple-system, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
            }}
            h1 {{
                text-align: center;
                color: #333;
            }}
            .info {{
                background: #e3f2fd;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <h1>Component Framework Demo (Litestar)</h1>

        <div class="info">
            <h3>How it works:</h3>
            <ul>
                <li>Server-side components with state management</li>
                <li>HTMX for dynamic updates</li>
                <li>No JavaScript framework required</li>
                <li>Click the buttons to interact!</li>
            </ul>
        </div>

        {result["html"]}

        <div class="info" style="margin-top: 30px;">
            <h3>Component State:</h3>
            <pre id="state-display">{result["state"]}</pre>
        </div>
    </body>
    </html>
    """

    return Response(content=html, media_type="text/html")


app = Litestar(route_handlers=[index, component_endpoint])

if __name__ == "__main__":
    import uvicorn

    print("Starting Component Framework Demo (Litestar)")
    print("Open http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
