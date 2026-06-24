"""Phase 1 public API: deterministic C4×Diátaxis skeleton — zero LLM calls, $0.

Reads GraphData and writes the full docs/ skeleton. Re-runs are idempotent:
only files whose source_sig drifted (or new) are regenerated; human-authored files
(no generated:true frontmatter) are never touched.
"""
from __future__ import annotations
from pathlib import Path

from ose_docgen import graph_reader as gr
from ose_docgen._tree_a import write_context, write_readme
from ose_docgen._tree_b import write_components, write_containers
from ose_docgen._tree_c import write_decisions, write_howto, write_meta, write_reference


def build_skeleton(
    gd: gr.GraphData,
    docs_dir: Path,
    sig: str,
    member_paths: list[str] | None = None,
    bpre_dir: Path | None = None,
) -> dict[str, str]:
    """Write the C4×Diátaxis skeleton. Returns {abs_path: 'written'|'skipped'}.

    Zero LLM calls. Idempotent on repeated runs with the same source_sig.
    Human-authored files (missing or generated:false frontmatter) are never modified.
    """
    mp = member_paths or []
    result: dict[str, str] = {}
    result.update(write_readme(docs_dir, gd, sig, mp))
    result.update(write_context(docs_dir, gd, sig, mp))
    result.update(write_containers(docs_dir, gd, sig, mp))
    result.update(write_components(docs_dir, gd, sig))
    result.update(write_reference(docs_dir, gd, sig))
    result.update(write_howto(docs_dir, sig, bpre_dir))
    result.update(write_decisions(docs_dir, sig))
    result.update(write_meta(docs_dir, gd, sig))
    return result
