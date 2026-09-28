"""Sphinx configuration for the Indriya docs.

Builds:
  - Hand-written Markdown (MyST) for narrative pages — mostly the existing
    docs/*.md usage guide, toctree'd as-is rather than duplicated
  - autodoc + napoleon for the ``mudra_sdk`` Python package

Layout assumed: this file lives at <repo>/docs/conf.py, and the importable
``mudra_sdk`` package lives at <repo>/mudra_sdk (no src/ layout, no installed
package — see docs/installation.md).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

sys.path.insert(0, str(REPO))


def _read_version() -> str:
    """Pull __version__ out of mudra_sdk/__init__.py without importing the
    package (autodoc imports it separately, under the mocks below)."""
    text = (REPO / "mudra_sdk" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return match.group(1) if match else "0.0.0"


project = "Indriya"
author = "Wearable Devices"
copyright = "2026, Wearable Devices"
release = _read_version()
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "myst_parser",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "CLAUDE.md",
    # Repo-internal file index for coding agents — superseded by this site's
    # own sidebar navigation, and full of relative links to files outside the
    # docs/ tree (../README.md, ../mudra_sdk/..., ../examples/...) that don't
    # resolve to pages in the built site.
    "DOCS_MAP.md",
]

html_theme = "furo"
templates_path = ["_templates"]
html_static_path = ["_static"]
# Load order matters: tokens.css defines the shared design tokens (layered on
# Furo's own light/dark theme variables) that every other sheet consumes, so
# it must come first. collapsible.css/js turn any
# ``.. container:: collapsible-code`` block into a native, collapsed-by-
# default <details> element; examples.css styles the example-app index cards,
# metadata bars, and license-tier badges reused on the examples/auth pages.
html_css_files = ["tokens.css", "collapsible.css", "examples.css", "led.css"]
html_js_files = ["collapsible.js"]
html_title = f"{project} {version}"
# The brand wordmark is white (built for a dark surface), so it shows in dark
# mode; brand-logo-dark.svg is the dark-ink variant for Furo's light sidebar.
html_favicon = "_static/brand-favicon.svg"
html_theme_options = {
    "light_logo": "brand-logo-dark.svg",
    "dark_logo": "brand-logo.svg",
    "sidebar_hide_name": True,
    "light_css_variables": {
        "color-brand-primary": "#0d7d6e",
        "color-brand-content": "#0d7d6e",
    },
    "dark_css_variables": {
        "color-brand-primary": "#5fd6cb",
        "color-brand-content": "#5fd6cb",
    },
}

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "member-order": "bysource",
}
# ``mudra_sdk`` imports ``bleak`` (BLE transport, a git-fork dependency) and
# ``smpclient`` (DFU/SMP transport) at module top; mock both so autodoc can
# import the package on the docs build host without installing them.
# ``pyserial``/``requests`` are lightweight pure-Python deps installed for
# real (see docs/requirements.txt). The native MudraSDK library is loaded
# lazily inside ``Mudra.__init__``, not at import time, so it needs no stub.
autodoc_mock_imports = ["bleak", "smpclient"]
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_use_ivar = True

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "linkify",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}


# ---------------------------------------------------------------------------
# Client-side fuzzy-search index.
#
# The docs ship on GitHub Pages (static hosting), so search must run entirely
# in the browser. We emit a small ``_static/search_index.json`` (one record
# per content page: url, title, plain-text body) during the HTML build; the
# search page loads it and runs MiniSearch with typo tolerance + a curated
# acronym/synonym map (``_static/fuzzy-search.js``). Stdlib only.
# ---------------------------------------------------------------------------
import json  # noqa: E402
from html.parser import HTMLParser  # noqa: E402

_SEARCH_SKIP_PAGES = {"search", "genindex", "py-modindex", "modindex"}


class _TextExtractor(HTMLParser):
    """Collect visible text from rendered page HTML, dropping script/style."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def text(self) -> str:
        return " ".join(self._chunks)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html or "")
    except Exception:  # never break the build over one odd page
        return ""
    return parser.text()


def _collect_page(app, pagename, templatename, context, doctree):
    if pagename in _SEARCH_SKIP_PAGES or pagename.startswith("_"):
        return
    body = context.get("body") or ""
    if not body:
        return
    title = _html_to_text(context.get("title") or pagename)
    text = _html_to_text(body)
    suffix = getattr(app.builder, "out_suffix", ".html")
    app.env.mp_search_docs.append(
        {"id": pagename, "url": pagename + suffix, "title": title, "text": text}
    )


def _write_index(app, exception):
    if exception is not None:
        return
    if getattr(app.builder, "format", "") != "html":
        return
    docs = getattr(app.env, "mp_search_docs", [])
    out = Path(app.outdir) / "_static" / "search_index.json"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(docs, ensure_ascii=False), encoding="utf-8")
        print(f"[conf.py] wrote fuzzy search index: {len(docs)} pages -> {out}")
    except OSError as exc:
        print(f"[conf.py] could not write search index ({exc}); "
              "fuzzy search will fall back to empty results.")


def setup(app):
    app.connect("builder-inited",
                lambda app: setattr(app.env, "mp_search_docs", []))
    app.connect("html-page-context", _collect_page)
    app.connect("build-finished", _write_index)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
