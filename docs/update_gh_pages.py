"""
docs/update_gh_pages.py — CI helper: update versions.json and root index.html.

Called by the docs CI workflow after copying a new version's docs into the
gh-pages working tree.  Scans version sub-directories, writes a machine-readable
versions.json, and regenerates the root index.html with a version listing.

Usage (from CI):
    python docs/update_gh_pages.py --pages-dir gh-pages-checkout/
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# ── Version detection ─────────────────────────────────────────────────────────

_RELEASE_RE = re.compile(r"^v\d+\.\d+")


def _semver_key(v: str) -> list:
    """Sort key for version strings: v1.2.3 < v1.2.3-alpha < v1.10.0."""
    parts = re.split(r"[.\-]", v.lstrip("v"))
    key = []
    for p in parts:
        try:
            key.append((0, int(p)))
        except ValueError:
            key.append((1, p))
    return key


def scan_versions(pages_dir: Path) -> tuple[list[str], str | None, bool]:
    """
    Scan *pages_dir* for documentation sub-directories.

    Returns:
        releases: Sorted list of release version strings (ascending).
        latest:   The highest release version, or None if there are none.
        has_main: True if a ``main/`` directory exists.
    """
    releases: list[str] = []
    has_main = False

    for entry in pages_dir.iterdir():
        if not entry.is_dir():
            continue
        if entry.name == "main":
            has_main = True
        elif _RELEASE_RE.match(entry.name):
            releases.append(entry.name)

    releases.sort(key=_semver_key)
    latest = releases[-1] if releases else None
    return releases, latest, has_main


# ── versions.json ─────────────────────────────────────────────────────────────


def write_versions_json(
    pages_dir: Path,
    releases: list[str],
    latest: str | None,
    has_main: bool,
) -> None:
    data = {
        "versions": releases,
        "latest": latest,
        "main": has_main,
    }
    path = pages_dir / "versions.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"  Wrote {path.name}: {len(releases)} release(s), latest={latest}, main={has_main}")


# ── Root index.html ───────────────────────────────────────────────────────────

_ROOT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>component-framework — Documentation</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');
    :root {{
      --bg:     #0a0c0b;
      --panel:  #0f1210;
      --border: #1e2b22;
      --green:  #7fff5f;
      --orange: #ff6e27;
      --cyan:   #1dfcf0;
      --dim:    #3a5043;
      --mid:    #698075;
      --text:   #c8d9cc;
      --white:  #e8f0ea;
      --mono:   'IBM Plex Mono', monospace;
    }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: var(--mono);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }}
    .card {{
      width: 100%;
      max-width: 560px;
      border: 1px solid var(--border);
      background: var(--panel);
    }}
    .card-header {{
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: baseline;
      gap: 1rem;
    }}
    .card-header h1 {{
      font-size: 1rem;
      color: var(--green);
      font-weight: 600;
    }}
    .card-header h1::before {{ content: "> "; color: var(--orange); }}
    .card-header .badge {{
      font-size: 9px;
      color: var(--orange);
      border: 1px solid var(--orange);
      padding: 1px 5px;
      letter-spacing: 0.1em;
      opacity: 0.8;
    }}
    .version-list {{
      list-style: none;
    }}
    .version-list li {{
      border-bottom: 1px solid var(--border);
    }}
    .version-list li:last-child {{ border-bottom: none; }}
    .version-list a {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.75rem 1.5rem;
      color: var(--mid);
      text-decoration: none;
      font-size: 13px;
      transition: background 0.12s, color 0.12s;
    }}
    .version-list a:hover {{
      background: rgba(127,255,95,0.04);
      color: var(--green);
    }}
    .version-list .tag {{
      font-size: 9px;
      padding: 1px 6px;
      border-radius: 2px;
      letter-spacing: 0.08em;
    }}
    .tag-dev     {{ color: var(--cyan);   border: 1px solid var(--cyan);   }}
    .tag-latest  {{ color: var(--green);  border: 1px solid var(--green);  }}
    .tag-release {{ color: var(--dim);    border: 1px solid var(--border); }}
    footer {{
      margin-top: 2rem;
      font-size: 10px;
      color: var(--dim);
      text-align: center;
    }}
    footer a {{ color: var(--dim); text-decoration: none; }}
    footer a:hover {{ color: var(--green); }}
  </style>
</head>
<body>
  <div class="card">
    <div class="card-header">
      <h1>component-framework</h1>
      <span class="badge">DOCS</span>
    </div>
    <ul class="version-list">
{items}
    </ul>
  </div>
  <footer>
    <a href="https://github.com/fsecada01/component-framework" target="_blank" rel="noopener">
      GitHub
    </a>
    &nbsp;·&nbsp; MIT license
  </footer>
</body>
</html>
"""

_LI_TEMPLATE = """\
      <li>
        <a href="{href}">
          <span>{label}</span>
          <span class="tag {tag_class}">{tag_text}</span>
        </a>
      </li>"""


def write_root_index(
    pages_dir: Path,
    releases: list[str],
    latest: str | None,
    has_main: bool,
) -> None:
    items: list[str] = []

    if has_main:
        items.append(
            _LI_TEMPLATE.format(
                href="main/component_framework/",
                label="main",
                tag_class="tag-dev",
                tag_text="dev",
            )
        )

    if latest:
        items.append(
            _LI_TEMPLATE.format(
                href="latest/component_framework/",
                label=f"latest  ({latest})",
                tag_class="tag-latest",
                tag_text="stable",
            )
        )

    for version in reversed(releases):
        tag_class = "tag-latest" if version == latest else "tag-release"
        tag_text = "latest" if version == latest else "release"
        items.append(
            _LI_TEMPLATE.format(
                href=f"{version}/component_framework/",
                label=version,
                tag_class=tag_class,
                tag_text=tag_text,
            )
        )

    html = _ROOT_HTML.format(items="\n".join(items))
    path = pages_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    print(f"  Wrote {path.name}")


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate versions.json and root index.html for gh-pages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--pages-dir",
        type=Path,
        required=True,
        metavar="DIR",
        help="Path to the gh-pages working tree checkout.",
    )
    args = parser.parse_args()

    pages_dir: Path = args.pages_dir
    if not pages_dir.is_dir():
        raise SystemExit(f"ERROR: --pages-dir does not exist: {pages_dir}")

    print(f"  Scanning {pages_dir} for version directories…")
    releases, latest, has_main = scan_versions(pages_dir)
    print(f"  Found: releases={releases}, latest={latest}, main={has_main}")

    write_versions_json(pages_dir, releases, latest, has_main)
    write_root_index(pages_dir, releases, latest, has_main)
    print("  Done.")


if __name__ == "__main__":
    main()
