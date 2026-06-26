"""Standalone repo parser: build GraphData from directory tree.

No OSE import, no tree-sitter. Derives symbols (=files) and L1 communities
(=top-level directories) by walking the source tree.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from ose_docgen.graph_reader import Community, Edge, GraphData, Symbol

_IGNORE_DIRS = frozenset({
    ".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache",
    "dist", "build", "target", ".cargo", ".gradle", "__snapshots__",
    "coverage", ".nyc_output", ".pytest_cache", ".tox",
})
_CODE_EXTS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".rs", ".rb",
    ".cpp", ".c", ".cs", ".php", ".swift", ".kt", ".scala", ".lua",
    ".sh", ".bash", ".yaml", ".yml", ".toml",
})


def _should_ignore(name: str) -> bool:
    return name in _IGNORE_DIRS or name.startswith(".")


def _iter_source_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in _CODE_EXTS:
            continue
        parts = p.relative_to(root).parts
        if not any(_should_ignore(part) for part in parts):
            result.append(p)
    return result


def _top_code_dirs(root: Path) -> list[str]:
    tops = sorted(
        d.name for d in root.iterdir()
        if d.is_dir()
        and not _should_ignore(d.name)
        and any(
            f.suffix in _CODE_EXTS
            for f in d.rglob("*")
            if f.is_file()
        )
    )
    return tops or ["__root__"]


def build_graph_data(project_path: Path) -> GraphData:
    """Build GraphData from directory tree (no AST, no graph.db)."""
    tops = _top_code_dirs(project_path)
    name_to_cid: dict[str, int] = {n: i for i, n in enumerate(tops, 1)}

    symbols: list[Symbol] = []
    cid_counts: dict[int, int] = {}
    for idx, f in enumerate(_iter_source_files(project_path)):
        rel = f.relative_to(project_path)
        top = rel.parts[0] if len(rel.parts) > 1 else "__root__"
        cid = name_to_cid.get(top)
        if cid:
            cid_counts[cid] = cid_counts.get(cid, 0) + 1
        symbols.append(Symbol(
            sid=f"f{idx}",
            name=f.stem,
            qualified_name=str(rel),
            kind="file",
            file=str(f),
            start_line=0,
            end_line=0,
            language=f.suffix.lstrip(".") or "text",
            community_id=cid,
        ))

    communities = [
        Community(
            community_id=name_to_cid[n],
            level=1,
            title=n.replace("_", " ").replace("-", " ").title(),
            summary=None,
            member_count=cid_counts.get(name_to_cid[n], 0),
            parent_id=None,
        )
        for n in tops
    ]

    dir_to_l1: dict[str, list[int]] = {}
    for s in symbols:
        if s.community_id:
            rel_str = str(Path(s.file).relative_to(project_path))
            top_dir = rel_str.split("/")[0] if "/" in rel_str else "__root__"
            bucket = dir_to_l1.setdefault(top_dir, [])
            if s.community_id not in bucket:
                bucket.append(s.community_id)

    return GraphData(
        project_path=project_path,
        algo_version="repo_parser_v1",
        symbols=symbols,
        communities=communities,
        edges=cast_edges([]),
        l1_communities=communities,
        l2_communities=[],
        dir_to_l1=dir_to_l1,
    )


def cast_edges(edges: list) -> list[Edge]:
    return edges


def compute_sig(project_path: Path) -> str:
    """Content-signature from the project file tree (mtime + sizes, GPU-free)."""
    total_size = 0
    latest_mtime = 0
    file_count = 0
    for p in sorted(project_path.rglob("*")):
        if p.is_file():
            try:
                st = p.stat()
                total_size += st.st_size
                latest_mtime = max(latest_mtime, st.st_mtime_ns)
                file_count += 1
            except OSError:
                pass
    raw = f"{project_path}:{latest_mtime}:{total_size}:{file_count}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]
