"""Emit _meta/MIGRATION.md — summary of every standardization run.

Idempotent: if sig unchanged and the set of classes is unchanged, MIGRATION.md
is provenance-gated (needs_regen returns False) and no write occurs.
"""
from __future__ import annotations

from pathlib import Path

from ose_docgen.provenance import HIER_VERSION, needs_regen, write_generated


def run(docs_dir: Path, sig: str, classify_result: dict) -> None:
    """Write _meta/MIGRATION.md. Only writes if sig has drifted."""
    migration_path = docs_dir / "_meta" / "MIGRATION.md"
    if not needs_regen(migration_path, sig):
        return

    n_gen = classify_result.get("generated", 0)
    n_human = classify_result.get("human", 0)
    n_asset = classify_result.get("asset", 0)
    dominated = classify_result.get("asset_dominated", False)
    classes: dict[str, str] = classify_result.get("classes", {})

    human_lines = "\n".join(
        f"- `{rel}` — preserved in place; see CROSSWALK.md for bucket assignment"
        for rel, cls in sorted(classes.items()) if cls == "human"
    )
    asset_lines = "\n".join(
        f"- `{rel}` — asset (not touched)"
        for rel, cls in sorted(classes.items()) if cls == "asset"
    )

    mode = " (coexist mode — asset-dominated tree)" if dominated else ""
    body = (
        f"# Migration Report\n\n"
        f"_hier_version: {HIER_VERSION}  sig: {sig[:8]}_\n\n"
        f"## Classification Summary{mode}\n\n"
        f"| Class | Count |\n|---|---|\n"
        f"| GENERATED (tool-owned) | {n_gen} |\n"
        f"| HUMAN-PROSE (preserved) | {n_human} |\n"
        f"| NON-DOC ASSET (skipped) | {n_asset} |\n"
    )
    if human_lines:
        body += f"\n## Human-Authored Files (preserved byte-for-byte)\n\n{human_lines}\n"
        body += "\nSee `CROSSWALK.md` for C4×Diátaxis bucket assignments.\n"
    if asset_lines:
        body += f"\n## Asset / Non-Prose Files (not touched)\n\n{asset_lines}\n"

    write_generated(migration_path, "meta", sig, body)
