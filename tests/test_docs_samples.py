"""The documentation's code samples are checked against the real package (#49).

Prose rots silently, and nothing here read the docs until this file existed.
Two dead samples were sitting in the tree when it was written, both of which
read perfectly:

* ``from component_framework.core.composition import SlotComponent,
  CompositeComponent`` — neither name exists. ``composition`` exports
  ``compose`` and ``SlotRenderer``. The surrounding README example was
  invented wholesale, down to a ``components = {...}`` attribute nothing
  reads.
* ``from component_framework import Component, registry`` — the top-level
  ``__init__`` exports only ``CorruptStateError`` and ``StateSigner``. Both
  names live in ``component_framework.core``.

Neither is the kind of thing review catches, because both are what you would
guess the API looks like. So the docs are parsed and their claims executed:
every ``python`` block must parse, and every name imported from
``component_framework`` must actually exist on the module it is imported
from.

Ported from cf-ui's ``tests/unit/test_docs_samples.py``, which exists for the
same reason — ``ComponentCatalog`` and ``<CfCard>`` sat in that README for
two releases.
"""

from __future__ import annotations

import ast
import importlib
import re
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent

#: Fenced blocks, including indented ones inside list items or admonitions —
#: the closing fence must match the opening fence's indent.
FENCE = re.compile(r"^([ \t]*)```(\w+)?[^\n]*\n(.*?)^\1```", re.M | re.S)

#: Docs that are published to a reader. ``docs/reports/`` is deliberately
#: excluded: those are point-in-time build records, not instructions, and
#: pinning their samples would freeze history rather than protect a reader.
DOC_GLOBS = ["README.md", "CONTRIBUTING.md", "docs/*.md", "docs/examples/*.md"]


def _doc_files() -> list[Path]:
    seen: dict[Path, None] = {}
    for pattern in DOC_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            seen[path] = None
    return list(seen)


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


DOC_FILES = _doc_files()


def test_the_doc_set_the_guard_walks_is_not_empty():
    """A guard over an empty glob passes. Pin what it is supposed to cover."""
    names = {_rel(p) for p in DOC_FILES}
    assert "README.md" in names
    for expected in ("docs/LOCKED_FIELDS.md", "docs/STATE_SIGNING.md", "docs/CBV_GUIDE.md"):
        assert expected in names, f"{expected} missing from the guarded doc set"


def _python_blocks() -> list[tuple[Path, str]]:
    out = []
    for path in DOC_FILES:
        text = path.read_text(encoding="utf-8")
        for match in FENCE.finditer(text):
            if (match.group(2) or "") in ("python", "py"):
                out.append((path, textwrap.dedent(match.group(3))))
    return out


PYTHON_BLOCKS = _python_blocks()


@pytest.mark.parametrize(
    ("path", "source"),
    PYTHON_BLOCKS,
    ids=[f"{_rel(p)}:{i}" for i, (p, _) in enumerate(PYTHON_BLOCKS)],
)
def test_every_python_sample_parses(path: Path, source: str):
    try:
        ast.parse(source)
    except SyntaxError as exc:
        pytest.fail(f"{_rel(path)}: sample does not parse: {exc}\n\n{source}")


def _imported_names() -> list[tuple[Path, str, str]]:
    """(file, module, name) for every documented ``from component_framework…``.

    Blocks that do not parse are skipped here rather than raising at
    collection time — ``test_every_python_sample_parses`` is what reports
    those, and a collection error would hide every other finding in this
    module behind it.
    """
    out = []
    for path, source in PYTHON_BLOCKS:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ImportFrom) and node.module and node.level == 0):
                continue
            if node.module != "component_framework" and not node.module.startswith(
                "component_framework."
            ):
                continue
            for alias in node.names:
                out.append((path, node.module, alias.name))
    return out


IMPORTED_NAMES = _imported_names()


@pytest.mark.parametrize(
    ("path", "module", "name"),
    IMPORTED_NAMES,
    ids=[f"{_rel(p)}:{m}.{n}" for p, m, n in IMPORTED_NAMES],
)
def test_every_documented_import_exists(path: Path, module: str, name: str):
    """``SlotComponent`` is the bug this test exists for.

    An adapter whose extra is not installed raises a deliberate, well-worded
    ``ImportError`` ("Install the 'django' extra: …"). That is the package
    working as designed, not a doc defect, so it is skipped —
    ``test_the_import_check_is_not_all_skips`` keeps that from hollowing the
    check out.
    """
    try:
        mod = importlib.import_module(module)
    except ImportError as exc:
        pytest.skip(f"optional dependency missing for {module}: {exc}")

    assert hasattr(mod, name), (
        f"{_rel(path)} documents `from {module} import {name}`, but {module} "
        f"exposes no such name. Available: "
        f"{', '.join(sorted(n for n in dir(mod) if not n.startswith('_'))[:12])}…"
    )


def test_the_import_check_is_not_all_skips():
    """At least the core imports must have been really checked.

    Every one of these resolves with no optional extra installed, so a skip
    here means the sample stopped being documented, not that the environment
    is thin.
    """
    checked = {(m, n) for _, m, n in IMPORTED_NAMES}
    for required in [
        ("component_framework.core", "Component"),
        ("component_framework.core", "registry"),
    ]:
        assert required in checked, (
            f"no doc sample imports {required[1]} from {required[0]} any more — "
            "either the docs regressed or this list is stale."
        )


def test_the_fence_regex_finds_the_blocks_it_claims_to():
    """Pin the extractor: a regex that stops matching reports clean forever."""
    doc = (
        "text\n\n```python\nx = 1\n```\n\n"
        "- item:\n\n    ```python\n    y = 2\n    ```\n\n"  # indented fence
        "```bash\nls\n```\n"
    )
    found = [(m.group(2), textwrap.dedent(m.group(3))) for m in FENCE.finditer(doc)]
    assert found == [("python", "x = 1\n"), ("python", "y = 2\n"), ("bash", "ls\n")]
    assert len(PYTHON_BLOCKS) >= 20, f"only {len(PYTHON_BLOCKS)} python samples found"


# ── The README's install instructions must describe the published package ──


#: Every phrasing of "you cannot install this from PyPI" that was in the file.
#: Matched loosely on purpose — the first cut of this guard pinned the exact
#: string "Not on PyPI" and sailed straight past a second, differently-worded
#: claim in the very first line of the same README.
NOT_ON_PYPI = re.compile(r"not (?:yet )?(?:on|published to) PyPI", re.I)


def test_the_readme_documents_installing_from_pypi():
    """The README *is* the PyPI landing page.

    Before #49 every install line was `pip install -e ".[extra]"` — an
    editable install from a checkout — and the file said twice that the
    package was not on PyPI. A visitor arriving from PyPI found no
    instruction that applied to them.
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    stale = NOT_ON_PYPI.search(readme)
    assert stale is None, (
        f"the README still claims the package is not on PyPI ({stale.group(0)!r}); "
        "it is published now"
    )
    assert re.search(r"(?:pip|uv) (?:pip )?(?:install|add) ['\"]?component-framework\[", readme), (
        "the README never shows `pip install component-framework[extra]` — the one "
        "line a reader arriving from the PyPI page needs."
    )


def test_the_not_on_pypi_guard_matches_both_phrasings_that_were_in_the_file():
    """Pin the loosened pattern against the two real sentences it replaced."""
    for phrasing in [
        "**Not on PyPI yet** — install from source:",
        "the public API can still change before 1.0. Not yet published to PyPI (see …).",
    ]:
        assert NOT_ON_PYPI.search(phrasing), phrasing
    assert NOT_ON_PYPI.search("This package is on PyPI.") is None


# ── README links have to work off GitHub too ───────────────────────────────

BLOB = "https://github.com/fsecada01/component-framework/blob/master/"
TREE = "https://github.com/fsecada01/component-framework/tree/master/"


def _readme_links() -> list[tuple[str, str]]:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    return re.findall(r"\[([^\]]+)\]\(([^)]+)\)", readme)


def test_every_readme_link_is_absolute():
    """The README renders on PyPI, where a relative link is a dead link.

    The docs site cannot cover for it either: that site is a pdoc API
    reference and does not publish the markdown guides at all. Anchors are
    fine — they resolve on both surfaces.
    """
    relative = [
        (label, target)
        for label, target in _readme_links()
        if not target.startswith(("http://", "https://", "#", "mailto:"))
    ]
    assert not relative, (
        "README links must be absolute so they work from the PyPI page: "
        + ", ".join(f"[{label}]({target})" for label, target in relative)
    )


def test_every_absolute_readme_link_into_this_repo_points_at_a_real_file():
    """An absolute link to a moved file 404s silently — worse than relative.

    Checked against ``git ls-files`` rather than the filesystem, because a
    path that exists locally but is untracked still 404s on github.com.
    """
    import subprocess

    tracked = set(
        subprocess.run(
            ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
    )
    assert tracked, "git ls-files returned nothing; this guard would pass vacuously"

    checked, dead = 0, []
    for _, url in _readme_links():
        for prefix in (BLOB, TREE):
            if not url.startswith(prefix):
                continue
            path = url[len(prefix) :].split("#")[0].rstrip("/")
            checked += 1
            # A directory target is fine if anything tracked lives under it.
            if path not in tracked and not any(t.startswith(path + "/") for t in tracked):
                dead.append(url)

    assert checked >= 15, f"only {checked} in-repo README links found; is the prefix stale?"
    assert not dead, "README links point at paths git does not track:\n  " + "\n  ".join(dead)
