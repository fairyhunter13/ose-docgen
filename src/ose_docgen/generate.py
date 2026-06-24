"""Data-contract entry point: generate() — the single function OSE calls.

Signature: generate(project_path, graph_db_path, member_db_paths, docs_dir, *, llm)
No opencode_search import. Reads graph.db as a versioned data contract.

Pipeline:
  Phase 1 (always): deterministic C4×Diátaxis skeleton, $0
  Phase 2 (if llm=True and OSE_DOCGEN_LLM=1): Haiku/Sonnet narration via Claude Code
"""
from __future__ import annotations

from pathlib import Path

from ose_docgen import config, migrate, standardize
from ose_docgen import graph_reader as gr
from ose_docgen.provenance import compute_sig, load_provenance, save_provenance
from ose_docgen.tree import build_skeleton


def generate(
    project_path: str | Path,
    graph_db_path: str | Path,
    member_db_paths: list[str] | None = None,
    docs_dir: str | Path | None = None,
    *,
    llm: bool | None = None,
) -> dict:
    """Generate or update the in-repo docs/ hierarchy.

    Args:
        project_path: Root of the repository to document.
        graph_db_path: Path to graph.db produced by opencode-search-engine.
        member_db_paths: Optional list of member graph.db paths (federated root).
        docs_dir: Output docs directory (default: <project_path>/docs/).
        llm: Override OSE_DOCGEN_LLM env flag (None = use env).

    Returns:
        dict with keys: written (list), skipped (list), errors (list), sig (str).
    """
    project_path = Path(project_path).resolve()
    graph_db_path = Path(graph_db_path)
    member_db_paths = [str(p) for p in (member_db_paths or [])]

    if docs_dir is None:
        docs_dir = project_path / config.DOCS_DIR
    docs_dir = Path(docs_dir)

    llm_on = config.LLM_ON if llm is None else bool(llm)

    # Load graph data
    gd = gr.load(graph_db_path, project_path)

    # Compute source signature (stat-only, GPU-free)
    sig = compute_sig(graph_db_path)

    # Phase 1: deterministic skeleton
    skeleton_result = build_skeleton(
        gd, docs_dir, sig,
        member_paths=member_db_paths,
    )

    written = [k for k, v in skeleton_result.items() if v == "written"]
    skipped = [k for k, v in skeleton_result.items() if v == "skipped"]
    errors: list[str] = []

    # Phase 2: narration (opt-in)
    if llm_on:
        from ose_docgen.narrate import narrate_significant
        narr = narrate_significant(gd, docs_dir, sig)
        for path_rel, status in narr.items():
            if status == "written":
                written.append(path_rel)
            elif status in ("error", "no_profile"):
                errors.append(f"{path_rel}:{status}")
            # 429 / skipped are benign

    # Phase 3: standardize/migrate (classify tree, build CROSSWALK.md + MIGRATION.md)
    classify_result = standardize.run(docs_dir, sig)
    migrate.run(docs_dir, sig, classify_result)

    # Update provenance
    meta_dir = docs_dir / "_meta"
    prov = load_provenance(meta_dir)
    prov["sig"] = sig
    prov["written"] = len(written)
    prov["skipped"] = len(skipped)
    prov["migration"] = {
        "generated": classify_result["generated"],
        "human": classify_result["human"],
        "asset": classify_result["asset"],
        "asset_dominated": classify_result["asset_dominated"],
    }
    save_provenance(meta_dir, prov)

    return {
        "written": written, "skipped": skipped, "errors": errors,
        "sig": sig, "migration": classify_result,
    }
