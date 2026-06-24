"""Tree writer — sections: 02-containers, 03-components."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ose_docgen import graph_reader as gr
from ose_docgen._tree_util import community_slug, mermaid_component, mermaid_container
from ose_docgen.provenance import needs_regen, write_generated

_NAR = "_(narration pending — run `OSE_DOCGEN_LLM=1 ose-docgen <root>`)_"


def write_containers(docs_dir: Path, gd: gr.GraphData, sig: str, members: list[str]) -> dict:
    out: dict = {}
    d = docs_dir / "02-containers"
    p = d / "overview.md"
    if needs_regen(p, sig):
        names = [gd.project_path.name] + [Path(m).name for m in members[:20]]
        rows = "\n".join(f"| `{n}` | — | [{n}.md]({n}.md) |" for n in names)
        body = (
            f"# Containers — {gd.project_path.name}\n\n"
            f"{mermaid_container(names)}\n\n"
            f"| Container | Role | Detail |\n|---|---|---|\n{rows}\n"
        )
        write_generated(p, "container", sig, body)
        out[str(p)] = "written"
    else:
        out[str(p)] = "skipped"
    for name, path in [(gd.project_path.name, str(gd.project_path))] + [
        (Path(m).name, m) for m in members[:24]
    ]:
        cp = d / f"{name}.md"
        if needs_regen(cp, sig):
            n = sum(1 for s in gd.symbols if s.file.startswith(path))
            write_generated(cp, "container", sig, f"# {name}\n\nSymbols: **{n}**\n\n{_NAR}\n")
            out[str(cp)] = "written"
        else:
            out[str(cp)] = "skipped"
    return out


def write_components(docs_dir: Path, gd: gr.GraphData, sig: str) -> dict:
    out: dict = {}
    d = docs_dir / "03-components"
    p = d / "overview.md"
    if needs_regen(p, sig):
        rows = "\n".join(
            f"| [{c.title or f'Domain {i}'}]({community_slug(c,i)}.md) | {c.member_count} | "
            f"{(c.summary or _NAR)[:100]} |"
            for i, c in enumerate(gd.l2_communities)
        ) or "_(no L2 communities yet)_"
        body = (
            f"# Components — {gd.project_path.name}\n\n"
            f"{mermaid_component(gd.l2_communities)}\n\n"
            f"| Domain | L1 count | Description |\n|---|---|---|\n{rows}\n"
        )
        write_generated(p, "component", sig, body)
        out[str(p)] = "written"
    else:
        out[str(p)] = "skipped"
    l2_to_l1: dict[int, list[gr.Community]] = defaultdict(list)
    for c in gd.l1_communities:
        if c.parent_id is not None:
            l2_to_l1[c.parent_id].append(c)
    for i, l2 in enumerate(gd.l2_communities):
        dp = d / f"{community_slug(l2, i)}.md"
        if needs_regen(dp, sig):
            children = l2_to_l1.get(l2.community_id, [])
            rows = "\n".join(
                f"| {c.title or f'Cluster {c.community_id}'} | {c.member_count} |"
                f" {(c.summary or _NAR)[:80]} |"
                for c in children
            )
            body = (
                f"# {l2.title or community_slug(l2,i)}\n\n"
                f"{l2.summary or _NAR}\n\n"
                f"| Community | Symbols | Description |\n|---|---|---|\n{rows or '_(none)_'}\n"
            )
            write_generated(dp, "component", sig, body)
            out[str(dp)] = "written"
        else:
            out[str(dp)] = "skipped"
    return out
