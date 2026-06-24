"""Shared utilities for the deterministic tree builder — no LLM calls."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from ose_docgen import graph_reader as gr


def rel(project_path: Path, abs_path: str) -> str:
    """Project-root-relative path — never exposes absolute device paths."""
    try:
        return str(Path(abs_path).relative_to(project_path))
    except ValueError:
        return Path(abs_path).name


def language_summary(symbols: list[gr.Symbol]) -> str:
    langs = Counter(s.language for s in symbols if s.language)
    if not langs:
        return ""
    return "Languages: " + ", ".join(f"{lang}({n})" for lang, n in langs.most_common(5))


def _safe_id(text: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", text.lower().replace(" ", "-"))[:40] or "domain"


def community_slug(c: gr.Community, idx: int) -> str:
    if c.title:
        slug = _safe_id(c.title)
        return slug if slug else f"domain-{idx}"
    return f"domain-{idx}"


def mermaid_container(names: list[str]) -> str:
    lines = ["```mermaid", "C4Container"]
    for n in names[:20]:
        lines.append(f'    Container(c_{_safe_id(n)}, "{n}", "", "")')
    lines.append("```")
    return "\n".join(lines)


def mermaid_component(l2: list[gr.Community]) -> str:
    if not l2:
        return ""
    lines = ["```mermaid", "C4Component"]
    for i, c in enumerate(l2[:20]):
        k = f"c{i}_{_safe_id(c.title or f'dom{c.community_id}')}"
        label = c.title or f"Domain {i}"
        lines.append(f'    Component({k}, "{label}", "", "")')
    lines.append("```")
    return "\n".join(lines)
