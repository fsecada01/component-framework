"""
docs/make.py — Static site generator for component-framework documentation.

Converts Markdown files in docs/ to HTML using pandoc, injecting each page
into docs/index.html (the layout template).

Usage:
    python docs/make.py                  # build all pages → docs/site/
    python docs/make.py --serve          # build + serve on http://localhost:8000
    python docs/make.py --check          # verify pandoc is available, dry-run

Requirements:
    pandoc >= 3.0  (https://pandoc.org/installing.html)
"""

from __future__ import annotations

import argparse
import http.server
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

DOCS_DIR = Path(__file__).parent
SITE_DIR = DOCS_DIR / "site"
LAYOUT = DOCS_DIR / "index.html"

# Ordered page registry. Each entry becomes a nav link + HTML file.
# fmt: off
PAGES: list[dict] = [
    # section, title, source_md, output_html, description
    {
        "section": "Getting Started",
        "title": "Introduction",
        "src": DOCS_DIR / "server_component_spec.md",
        "out": "index.html",
        "desc": "Framework-agnostic server-side components with LiveView-style interactivity.",
    },
    {
        "section": "Getting Started",
        "title": "Build Status",
        "src": DOCS_DIR / "reports" / "BUILD_COMPLETE.md",
        "out": "build-complete.html",
        "desc": "Implementation summary and current build status.",
    },
    {
        "section": "Django",
        "title": "Django Integration",
        "src": DOCS_DIR / "DJANGO_IMPLEMENTATION.md",
        "out": "django.html",
        "desc": "Complete guide to using component-framework with Django.",
    },
    {
        "section": "Django",
        "title": "Class-Based Views",
        "src": DOCS_DIR / "CBV_GUIDE.md",
        "out": "cbv-guide.html",
        "desc": "ComponentView, AuthenticatedComponentView, PermissionComponentView, and mixins.",
    },
    {
        "section": "Examples",
        "title": "E-Commerce Live View",
        "src": DOCS_DIR / "examples" / "ecommerce.md",
        "out": "examples/ecommerce.html",
        "desc": "Real-time product page and shopping cart with optimistic UI — no React required.",
    },
]
# fmt: on

PANDOC_ARGS = [
    "--from=gfm",
    "--to=html5",
    "--syntax-highlighting=none",  # we do our own minimal highlighting via CSS
    "--wrap=none",
]


# ── Data model ───────────────────────────────────────────────────────────────


@dataclass
class Page:
    section: str
    title: str
    src: Path
    out: str
    desc: str

    @property
    def out_path(self) -> Path:
        return SITE_DIR / self.out

    @property
    def missing(self) -> bool:
        return not self.src.exists()


def load_pages() -> list[Page]:
    return [Page(**p) for p in PAGES]


# ── Pandoc invocation ────────────────────────────────────────────────────────


def check_pandoc() -> str:
    """Return pandoc version string or exit with a helpful message."""
    pandoc = shutil.which("pandoc")
    if not pandoc:
        sys.exit(
            "ERROR: pandoc not found.\n"
            "Install it from https://pandoc.org/installing.html\n"
            "  macOS:   brew install pandoc\n"
            "  Ubuntu:  sudo apt install pandoc\n"
            "  Windows: winget install JohnMacFarlane.Pandoc\n"
        )
    result = subprocess.run(
        [pandoc, "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    version_line = result.stdout.splitlines()[0]
    return version_line


def markdown_to_html(src: Path) -> str:
    """Convert a Markdown file to an HTML fragment via pandoc."""
    result = subprocess.run(
        ["pandoc", *PANDOC_ARGS, str(src)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"pandoc failed on {src}:\n{result.stderr}")
    return result.stdout


# ── Navigation builder ───────────────────────────────────────────────────────


def build_nav(pages: list[Page], current_out: str) -> str:
    """Return a sidebar <nav> HTML string with sections and links."""
    sections: dict[str, list[Page]] = {}
    for page in pages:
        sections.setdefault(page.section, []).append(page)

    lines: list[str] = []
    for section, section_pages in sections.items():
        lines.append('<div class="nav-section">')
        lines.append(f'  <span class="nav-section__label">{section}</span>')
        lines.append("  <ul>")
        for page in section_pages:
            # compute relative href from current page's directory
            current_depth = current_out.count("/")
            if current_depth == 0:
                href = page.out
            else:
                prefix = "../" * current_depth
                href = prefix + page.out
            active = ' class="active"' if page.out == current_out else ""
            lines.append(f'    <li><a href="{href}"{active}>{page.title}</a></li>')
        lines.append("  </ul>")
        lines.append("</div>")

    return "\n".join(lines)


# ── Layout injection ──────────────────────────────────────────────────────────


def render_page(layout: str, page: Page, content_html: str, nav_html: str) -> str:
    """Substitute placeholders in the layout template."""
    out = layout
    out = out.replace("{{TITLE}}", page.title)
    out = out.replace("{{DESCRIPTION}}", page.desc)
    out = out.replace("{{NAV}}", nav_html)
    out = out.replace("{{CONTENT}}", content_html)
    return out


# ── Build pipeline ────────────────────────────────────────────────────────────


def build(pages: list[Page], layout_text: str, *, verbose: bool = True) -> int:
    """Build all pages into SITE_DIR. Returns number of pages built."""
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "examples").mkdir(exist_ok=True)

    built = 0
    skipped = 0

    for page in pages:
        if page.missing:
            if verbose:
                print(f"  SKIP  {page.src.name!s:40s}  (not found)")
            skipped += 1
            continue

        if verbose:
            print(f"  BUILD {page.src.name!s:40s}  -> {page.out}")

        try:
            content_html = markdown_to_html(page.src)
        except RuntimeError as exc:
            print(f"  ERROR {exc}", file=sys.stderr)
            continue

        nav_html = build_nav(pages, page.out)
        full_html = render_page(layout_text, page, content_html, nav_html)

        page.out_path.parent.mkdir(parents=True, exist_ok=True)
        page.out_path.write_text(full_html, encoding="utf-8")
        built += 1

    # copy any static assets (CSS, JS, images) from docs/static/ if present
    static_src = DOCS_DIR / "static"
    if static_src.is_dir():
        static_dst = SITE_DIR / "static"
        if static_dst.exists():
            shutil.rmtree(static_dst)
        shutil.copytree(static_src, static_dst)
        if verbose:
            print("  COPY  static/ -> site/static/")

    if verbose:
        print(f"\n  {built} page(s) built, {skipped} skipped -> {SITE_DIR}")

    return built


# ── Dev server ────────────────────────────────────────────────────────────────


def serve(port: int = 8000) -> None:
    """Start a simple HTTP server rooted at SITE_DIR."""
    os.chdir(SITE_DIR)

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            # suppress verbose per-request logging
            pass

    server = http.server.HTTPServer(("", port), _Handler)
    print(f"  Serving docs at http://localhost:{port}/")
    print("  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build component-framework documentation site.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--serve", action="store_true", help="Build then start dev server")
    parser.add_argument("--port", type=int, default=8000, help="Dev server port (default: 8000)")
    parser.add_argument("--check", action="store_true", help="Verify pandoc and list pages")
    parser.add_argument("--quiet", action="store_true", help="Suppress build output")
    args = parser.parse_args()

    version = check_pandoc()
    print(f"  {version}")

    if args.check:
        pages = load_pages()
        print(f"\n  Pages ({len(pages)}):")
        for page in pages:
            status = "OK" if not page.missing else "MISSING"
            print(f"    [{status}] {page.title:30s}  {page.src.relative_to(DOCS_DIR)}")
        return

    if not LAYOUT.exists():
        sys.exit(f"ERROR: layout template not found: {LAYOUT}")

    layout_text = LAYOUT.read_text(encoding="utf-8")
    pages = load_pages()

    verbose = not args.quiet
    if verbose:
        print(f"\n  Building {len(pages)} page(s) -> {SITE_DIR}\n")

    built = build(pages, layout_text, verbose=verbose)

    if built == 0:
        sys.exit("ERROR: no pages were built.")

    if args.serve:
        print()
        serve(port=args.port)


if __name__ == "__main__":
    main()
