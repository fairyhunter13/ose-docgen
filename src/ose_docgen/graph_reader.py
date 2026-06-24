"""Minimal read-only graph.db reader — no opencode_search import.

Data-contract boundary: reads graph.db as a versioned SQLite schema (fg1+lp2 from OSE).
Schema: symbols, edges, communities(level 1/2), meta(algo_version).
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Symbol:
    sid: str
    name: str
    qualified_name: str
    kind: str
    file: str
    start_line: int
    end_line: int
    language: str
    community_id: int | None


@dataclass(frozen=True)
class Community:
    community_id: int
    level: int
    title: str | None
    summary: str | None
    member_count: int
    parent_id: int | None


@dataclass(frozen=True)
class Edge:
    caller_sid: str
    callee_sid: str


@dataclass
class GraphData:
    """Fully-loaded snapshot of one graph.db, with paths made project-root-relative."""
    project_path: Path
    algo_version: str | None
    symbols: list[Symbol] = field(default_factory=list)
    communities: list[Community] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    l1_communities: list[Community] = field(default_factory=list)
    l2_communities: list[Community] = field(default_factory=list)
    dir_to_l1: dict[str, list[int]] = field(default_factory=dict)


def _rel(project_path: Path, file: str) -> str:
    """Project-root-relative path — never exposes absolute device paths."""
    try:
        return str(Path(file).relative_to(project_path))
    except ValueError:
        return Path(file).name


def load(graph_db: Path, project_path: Path) -> GraphData:
    """Load graph.db into a GraphData snapshot (read-only, no opencode_search import)."""
    if not graph_db.exists():
        raise FileNotFoundError(f"graph.db not found: {graph_db}")

    con = sqlite3.connect(f"file:{graph_db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        algo_version: str | None = None
        try:
            row = con.execute("SELECT value FROM meta WHERE key='algo_version'").fetchone()
            if row:
                algo_version = row["value"]
        except sqlite3.OperationalError:
            pass

        symbols = [
            Symbol(
                sid=r["sid"], name=r["name"],
                qualified_name=r["qualified_name"] or r["name"],
                kind=r["kind"] or "", file=r["file"] or "",
                start_line=r["start_line"] or 0, end_line=r["end_line"] or 0,
                language=r["language"] or "", community_id=r["community_id"],
            )
            for r in con.execute(
                "SELECT sid,name,qualified_name,kind,file,start_line,end_line,language,community_id"
                " FROM symbols"
            )
        ]
        communities = [
            Community(
                community_id=r["id"], level=r["level"],
                title=r["title"], summary=r["summary"],
                member_count=r["member_count"] or 0, parent_id=r["parent_id"],
            )
            for r in con.execute(
                "SELECT id,level,title,summary,member_count,parent_id"
                " FROM communities ORDER BY level,id"
            )
        ]
        edges = [
            Edge(caller_sid=r["caller_sid"], callee_sid=r["callee_sid"])
            for r in con.execute("SELECT caller_sid,callee_sid FROM edges")
        ]
    finally:
        con.close()

    l1 = [c for c in communities if c.level == 1]
    l2 = [c for c in communities if c.level == 2]
    l1_ids = {c.community_id for c in l1}

    dir_to_l1: dict[str, list[int]] = {}
    for sym in symbols:
        if sym.community_id not in l1_ids or not sym.file:
            continue
        rel = _rel(project_path, sym.file)
        top = rel.split("/")[0] if "/" in rel else "__root__"
        bucket = dir_to_l1.setdefault(top, [])
        if sym.community_id not in bucket:
            bucket.append(sym.community_id)

    return GraphData(
        project_path=project_path, algo_version=algo_version,
        symbols=symbols, communities=communities, edges=edges,
        l1_communities=l1, l2_communities=l2, dir_to_l1=dir_to_l1,
    )


def iter_entry_points(gd: GraphData) -> Iterator[Symbol]:
    """Yield symbols that look like entry points (main/run/handler/etc.)."""
    entry_kinds = {"function", "method", "class"}
    entry_names = {"main", "run", "start", "init", "handler", "cmd", "serve", "app"}
    for sym in gd.symbols:
        if sym.kind in entry_kinds and sym.name.lower() in entry_names:
            yield sym
