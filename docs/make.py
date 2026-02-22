"""
docs/make.py — API documentation builder for component-framework.

Generates an HTML API reference from Python docstrings using pdoc.
The output is a self-contained static site suitable for GitHub Pages.

Uses pdoc's Python API (not the CLI) so that Django can be initialised
before the package is imported — required because the Django adapters
import from django.contrib.auth at module scope.

Usage:
    python docs/make.py                   # build -> docs/site/
    python docs/make.py --serve           # start pdoc dev server (localhost:8000)
    python docs/make.py --check           # verify pdoc is available, print config
    python docs/make.py -o /tmp/my-docs   # custom output directory

Requirements:
    pdoc >= 14  (pip install pdoc  OR  uv pip install pdoc)
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

DOCS_DIR = Path(__file__).parent
REPO_ROOT = DOCS_DIR.parent
SRC_DIR = REPO_ROOT / "src"
PACKAGE = "component_framework"
TEMPLATES_DIR = DOCS_DIR / "pdoc_templates"
DEFAULT_OUT = DOCS_DIR / "site"


# ── Environment bootstrap ─────────────────────────────────────────────────────


def _configure_environment() -> None:
    """
    Extend sys.path and configure Django settings before pdoc imports the package.

    The Django adapters import from ``django.contrib.auth`` at module scope, which
    requires both ``DJANGO_SETTINGS_MODULE`` to be set **and** ``django.setup()``
    to have been called before the first import.  This function handles both.
    """
    # Make src/ importable (component_framework) and repo root importable (docs.*)
    for p in [str(SRC_DIR), str(REPO_ROOT)]:
        if p not in sys.path:
            sys.path.insert(0, p)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "docs.docs_settings")

    import django

    django.setup()


# ── Build ─────────────────────────────────────────────────────────────────────


def build(output_dir: Path) -> None:
    """Generate static HTML docs into *output_dir* via pdoc's Python API."""
    _configure_environment()

    import pdoc
    import pdoc.render

    pdoc.render.configure(
        template_directory=TEMPLATES_DIR,
        docformat="google",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    pdoc.pdoc(PACKAGE, output_directory=output_dir)

    # Copy custom site pages (home, examples) into the output root.
    site_pages_dir = DOCS_DIR / "site-pages"
    if site_pages_dir.is_dir():
        pages = list(site_pages_dir.glob("*.html"))
        for page in pages:
            shutil.copy2(page, output_dir / page.name)
        print(f"  Copied {len(pages)} site page(s) from {site_pages_dir.name}/")


# ── Dev server ────────────────────────────────────────────────────────────────


def serve(host: str = "localhost", port: int = 8000) -> None:
    """Start pdoc's built-in live-reloading dev server."""
    _configure_environment()

    import pdoc.render
    import pdoc.web

    pdoc.render.configure(
        template_directory=TEMPLATES_DIR,
        docformat="google",
    )

    server = pdoc.web.DocServer((host, port), [PACKAGE])
    print(f"  Serving docs at http://{host}:{port}/")
    print("  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


# ── CLI ────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build component-framework API docs with pdoc.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=DEFAULT_OUT,
        metavar="DIR",
        help="Output directory (default: docs/site/)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start pdoc's built-in dev server instead of writing files",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Dev-server port (default: 8000)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify pdoc is available and print configuration, then exit",
    )
    args = parser.parse_args()

    # Verify pdoc is importable and report its version
    try:
        import pdoc as _pdoc

        pdoc_version = _pdoc.__version__
    except ImportError:
        sys.exit(
            "ERROR: pdoc not found.\n"
            "  Install with:  uv pip install pdoc\n"
            "  Or:            pip install pdoc\n"
        )

    print(f"  pdoc {pdoc_version}")

    if args.check:
        print(f"  Package   : {PACKAGE}")
        print(f"  Source    : {SRC_DIR}")
        print(f"  Templates : {TEMPLATES_DIR}")
        print(f"  Output    : {args.output_dir}")
        return

    if args.serve:
        serve(port=args.port)
        return

    print(f"\n  Building API docs -> {args.output_dir}\n")
    build(args.output_dir)
    print(f"\n  Done. API ref: {args.output_dir / PACKAGE}.html")
    print(f"        Home:    {args.output_dir}/index.html")


if __name__ == "__main__":
    main()
