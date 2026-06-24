"""Tree writer — sections: 04-reference, 05-how-to, 06-decisions, _meta."""
from __future__ import annotations
from pathlib import Path
from ose_docgen import graph_reader as gr
from ose_docgen._tree_util import rel
from ose_docgen.provenance import HIER_VERSION, needs_regen, write_generated

_SON = "_(Sonnet synthesis — run `OSE_DOCGEN_LLM=1 OSE_DOCGEN_TIER=sonnet ose-docgen <root>`)_"


def write_reference(docs_dir: Path, gd: gr.GraphData, sig: str) -> dict:
    out: dict = {}
    d = docs_dir / "04-reference"
    p = d / "dependency-map.md"
    if needs_regen(p, sig):
        sid_to_file = {s.sid: rel(gd.project_path, s.file) for s in gd.symbols if s.file}
        fedges: set[tuple[str, str]] = set()
        for e in gd.edges:
            fa, fb = sid_to_file.get(e.caller_sid), sid_to_file.get(e.callee_sid)
            if fa and fb and fa != fb:
                fedges.add((fa, fb))
        top = list(fedges)[:40]
        lines = (
            ["```mermaid", "graph TD"]
            + [f"    {Path(a).stem.replace('-','_')} --> {Path(b).stem.replace('-','_')}" for a, b in top]
            + ["```"]
        )
        write_generated(p, "code", sig, (
            f"# Dependency Map — {gd.project_path.name}\n\n"
            f"Top {len(top)} of {len(fedges)} file-level edges.\n\n"
            + "\n".join(lines) + "\n"
        ))
        out[str(p)] = "written"
    else:
        out[str(p)] = "skipped"
    dm = d / "data-model.md"
    if needs_regen(dm, sig):
        write_generated(dm, "code", sig, f"# Data Model — {gd.project_path.name}\n\n{_SON}\n")
        out[str(dm)] = "written"
    else:
        out[str(dm)] = "skipped"
    return out


def write_howto(docs_dir: Path, sig: str, bpre_dir: Path | None) -> dict:
    p = docs_dir / "05-how-to" / "processes" / "_index.md"
    if not needs_regen(p, sig):
        return {str(p): "skipped"}
    if bpre_dir and bpre_dir.exists():
        links = "\n".join(f"- [{f.stem}]({f})" for f in sorted(bpre_dir.glob("*.md"))[:20])
        body = f"# Processes\n\nBPRE process flows.\n\n{links or '_(none)_'}\n"
    else:
        body = "# Processes\n\n_No BPRE processes indexed yet._\n"
    write_generated(p, "meta", sig, body)
    return {str(p): "written"}


def write_decisions(docs_dir: Path, sig: str) -> dict:
    p = docs_dir / "06-decisions" / "_index.md"
    if not needs_regen(p, sig):
        return {str(p): "skipped"}
    write_generated(p, "meta", sig, f"# Architectural Decisions\n\n{_SON}\n")
    return {str(p): "written"}


def write_meta(docs_dir: Path, gd: gr.GraphData, sig: str) -> dict:
    p = docs_dir / "_meta" / "HIERARCHY.md"
    if not needs_regen(p, sig):
        return {str(p): "skipped"}
    body = (
        f"# Information Hierarchy — {gd.project_path.name}\n\n"
        f"**Standard:** C4 × Diátaxis × ADR | **Tool:** ose-docgen | **Contract:** fg1+lp2\n\n"
        f"| Section | C4 | Diátaxis | Source |\n|---|---|---|---|\n"
        f"| 01-context/ | Context | explanation | L3 federation |\n"
        f"| 02-containers/ | Container | reference | members / modules |\n"
        f"| 03-components/ | Component | explanation | L1/L2 communities |\n"
        f"| 04-reference/ | Code | reference | symbols + edges |\n"
        f"| 05-how-to/ | — | how-to | BPRE processes |\n"
        f"| 06-decisions/ | — | explanation | ADRs (Sonnet) |\n\n"
        f"`generated:true` = tool-owned · others = human-authored (never overwritten).\n"
        f"Graph sig: `{sig[:8]}` · Hier: `{HIER_VERSION}`\n"
    )
    write_generated(p, "meta", sig, body)
    return {str(p): "written"}
