"""Template loader for the local CML tool."""

from pathlib import Path


TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "index.html"


def load_page():
    """Return the packaged application shell."""
    return TEMPLATE_PATH.read_text(encoding="utf-8")


PAGE = load_page()
