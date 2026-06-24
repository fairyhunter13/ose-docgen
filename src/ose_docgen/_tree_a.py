"""Tree writer — sections: README, 01-context."""
from __future__ import annotations

from pathlib import Path

from ose_docgen import graph_reader as gr
from ose_docgen._tree_util import language_summary
from ose_docgen.provenance import needs_regen, write_generated

_NAR = "_(narration pending — run `OSE_DOCGEN_LLM=1 ose-docgen <root>`)_"
_SON = "_(Sonnet synthesis — run `OSE_DOCGEN_LLM=1 OSE_DOCGEN_TIER=sonnet ose-docgen <root>`)_"


def write_readme(docs_dir: Path, gd: gr.GraphData, sig: str, members: list[str]) -> dict:
    p = docs_dir / "README.md"
    if not needs_regen(p, sig):
        return {str(p): "skipped"}
    nav = (
        "| [01-context/](01-context/) | Context | System boundary |\n"
        "| [02-containers/](02-containers/) | Container | Services |\n"
        "| [03-components/](03-components/) | Component | Domain map |\n"
        "| [04-reference/](04-reference/) | Code | Symbols, graph |\n"
        "| [05-how-to/](05-how-to/) | — | Processes |\n"
        "| [06-decisions/](06-decisions/) | — | ADRs |"
    )
    member_list = "\n".join(f"- `{Path(m).name}`" for m in members[:30])
    body = (
        f"# {gd.project_path.name} — Documentation\n\n"
        f"> Auto-generated · C4×Diátaxis · {language_summary(gd.symbols)}\n\n"
        f"| Metric | Value |\n|---|---|\n"
        f"| Symbols | {len(gd.symbols)} |\n"
        f"| L1 communities | {len(gd.l1_communities)} |\n"
        f"| L2 domains | {len(gd.l2_communities)} |\n\n"
        f"## Navigation\n\n| Section | C4 | Content |\n|---|---|---|\n{nav}\n\n"
    )
    if member_list:
        body += f"## Federated members\n\n{member_list}\n\n"
    body += "_See [_meta/HIERARCHY.md](_meta/HIERARCHY.md) for the standard._\n"
    write_generated(p, "meta", sig, body)
    return {str(p): "written"}


def write_context(docs_dir: Path, gd: gr.GraphData, sig: str, members: list[str]) -> dict:
    out: dict = {}
    d = docs_dir / "01-context"
    p = d / "system-context.md"
    if needs_regen(p, sig):
        ml = "\n".join(f"  - `{Path(m).name}`" for m in members) or "  _(standalone)_"
        _name = gd.project_path.name
        _sid = _name.replace("-", "_")
        body = (
            f"# System Context — {_name}\n\n<!-- expand: OSE_DOCGEN_TIER=sonnet -->\n\n"
            f"**Root:** `{_name}`\n\n**Members:**\n{ml}\n\n{_SON}\n\n"
            f"```mermaid\nC4Context\n"
            f'    System(s_{_sid}, "{_name}", "")\n```\n'
        )
        write_generated(p, "context", sig, body)
        out[str(p)] = "written"
    else:
        out[str(p)] = "skipped"
    g = d / "glossary.md"
    if needs_regen(g, sig):
        terms = "\n".join(
            f"- **{c.title}**: {_NAR}" for c in gd.l1_communities[:30] if c.title
        )
        write_generated(g, "context", sig, f"# Glossary — {gd.project_path.name}\n\n{terms}\n")
        out[str(g)] = "written"
    else:
        out[str(g)] = "skipped"
    return out
