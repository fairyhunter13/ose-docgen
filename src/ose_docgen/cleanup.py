"""Remove generated docs from a docs_dir, preserving human and asset files.

Entry point: clean_generated(docs_dir) -> {"removed": [...], "preserved": [...], "pruned_dirs": [...]}
"""
from __future__ import annotations

from pathlib import Path

from .provenance import classify


def clean_generated(docs_dir: str | Path) -> dict:
    """Remove every generated file + _meta/ tree from docs_dir.

    Preserves human and asset files byte-for-byte. Prunes empty dirs bottom-up.
    Removes docs_dir itself if it ends empty. Idempotent.
    """
    root = Path(docs_dir)
    if not root.exists():
        return {"removed": [], "preserved": [], "pruned_dirs": []}

    removed: list[str] = []
    preserved: list[str] = []

    for f in sorted(root.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(root)
        if "_meta" in rel.parts:  # tool-owned subtree — always remove
            f.unlink()
            removed.append(str(rel))
        elif classify(f) == "generated":
            f.unlink()
            removed.append(str(rel))
        else:
            preserved.append(str(rel))

    # Prune empty dirs bottom-up (deepest first)
    pruned: list[str] = []
    all_dirs = sorted(
        (d for d in root.rglob("*") if d.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for d in all_dirs:
        if d.exists() and not any(d.iterdir()):
            pruned.append(str(d.relative_to(root)))
            d.rmdir()
    if root.exists() and not any(root.iterdir()):
        pruned.append(".")
        root.rmdir()

    return {"removed": removed, "preserved": preserved, "pruned_dirs": pruned}
