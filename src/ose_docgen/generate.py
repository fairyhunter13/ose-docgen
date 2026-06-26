"""Standalone entry point: generate() — LLM-native IH authoring via claude -p.

Signature: generate(project_path, docs_dir=None, *, member_paths=None)
No opencode_search import. No graph.db required.

Kill-switch: OSE_DOCGEN=0 → returns empty dict immediately (no output).
No deterministic skeleton — LLM (claude -p) is the only generation path.
"""
from __future__ import annotations

from pathlib import Path

from ose_docgen import config
from ose_docgen.portal import portal


def generate(
    project_path: str | Path,
    docs_dir: str | Path | None = None,
    *,
    member_paths: list[str] | None = None,
    llm: bool | None = None,
    graph_db_path: object = None,
    member_db_paths: object = None,
) -> dict:
    """Generate IH docs via claude -p. Kill-switch: OSE_DOCGEN=0 → no output."""
    if graph_db_path is not None:
        raise TypeError("graph_db_path is no longer accepted — docgen is standalone")
    if member_db_paths is not None:
        raise TypeError("member_db_paths is no longer accepted — pass member_paths (repo dirs)")

    project_path = Path(project_path).resolve()
    if docs_dir is None:
        docs_dir = project_path / config.DOCS_DIR
    docs_dir = Path(docs_dir)

    import os
    if os.environ.get("OSE_DOCGEN", "1") == "0":
        return {"written": [], "skipped": [], "errors": [], "sig": "", "mode": "off"}

    return portal(project_path, docs_dir=docs_dir, member_paths=member_paths or [])
