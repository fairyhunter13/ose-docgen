"""Classify docs/ tree: generated / human / asset."""
from __future__ import annotations

from pathlib import Path

from ose_docgen.provenance import classify

_STANDARD_BUCKETS = ["information-hierarchy", "_meta"]


def is_asset_dominated(docs_dir: Path) -> bool:
    n_prose = n_other = 0
    prose_sfx = {".md", ".mdx", ".rst", ".txt"}
    for f in docs_dir.rglob("*"):
        if f.is_file():
            if f.suffix.lower() in prose_sfx:
                n_prose += 1
            else:
                n_other += 1
    return n_other > 0 and n_other > n_prose


def classify_tree(docs_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not docs_dir.exists():
        return result
    for f in sorted(docs_dir.rglob("*")):
        if f.is_file():
            result[str(f.relative_to(docs_dir))] = classify(f)
    return result


def run(docs_dir: Path, sig: str) -> dict:
    """Classify the docs tree; return summary counts."""
    classes = classify_tree(docs_dir)
    n_gen = sum(1 for c in classes.values() if c == "generated")
    n_human = sum(1 for c in classes.values() if c == "human")
    n_asset = sum(1 for c in classes.values() if c == "asset")
    dominated = is_asset_dominated(docs_dir) if docs_dir.exists() else False
    return {
        "generated": n_gen, "human": n_human, "asset": n_asset,
        "classes": classes, "asset_dominated": dominated,
    }
