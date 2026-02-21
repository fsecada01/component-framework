"""FastAPI example application with Counter component."""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from jinjax import Catalog

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from component_framework.adapters.fastapi import create_component_routes
from component_framework.adapters.jinjax_renderer import JinjaxRenderer
from component_framework.components.counter import Counter
from component_framework.core import Component

# Initialize FastAPI
app = FastAPI(title="Component Framework Demo")

# Setup Jinjax
templates_dir = Path(__file__).parent.parent / "templates" / "components"
catalog = Catalog()
catalog.add_folder(templates_dir)
catalog.jinja_env.autoescape = True

# Configure renderer globally for all components
renderer = JinjaxRenderer(catalog)
Component.renderer = renderer

# Add component routes
create_component_routes(app)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve demo page."""
    # Initial render of counter
    counter = Counter(initial=0)
    result = counter.dispatch()

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Component Framework Demo</title>
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
        <h1>Component Framework Demo</h1>

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


if __name__ == "__main__":
    import uvicorn

    print("Starting Component Framework Demo")
    print("Open http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
