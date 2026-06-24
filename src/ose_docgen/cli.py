"""Standalone CLI: ose-docgen <root> [--graph graph.db] [--docs-dir docs/] [--llm]

Usable outside the OSE daemon — runs Phase 1 + optional Phase 2 on any indexed project.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ose-docgen",
        description="Generate a C4×Diátaxis information hierarchy for any repository.",
    )
    p.add_argument("root", help="Repository root path to document")
    p.add_argument("--graph", default=None,
                   help="Path to graph.db (default: <OSE_DATA_DIR>/<project>/graph.db)")
    p.add_argument("--docs-dir", default=None,
                   help="Output docs directory (default: <root>/docs/)")
    p.add_argument("--llm", action="store_true",
                   help="Enable Claude narration (Haiku 4.5; requires subscription creds)")
    p.add_argument("--members", nargs="*", default=None,
                   help="Additional member project paths (federated root)")
    args = p.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 1

    # Locate graph.db
    if args.graph:
        graph_db = Path(args.graph)
    else:
        # OSE stores indexes as ~/.local/share/opencode-search/indexes/<name>-<hash>/graph.db
        data_root = Path.home() / ".local" / "share" / "opencode-search"
        index_root = data_root / "indexes"
        candidates = (
            sorted(index_root.glob(f"{root.name}-*/graph.db")) if index_root.exists() else []
        )
        if len(candidates) == 1:
            graph_db = candidates[0]
        elif len(candidates) > 1:
            print(f"warning: multiple index dirs for '{root.name}' — using newest", file=sys.stderr)
            graph_db = max(candidates, key=lambda p: p.stat().st_mtime)
        else:
            graph_db = root / "graph.db"  # bare fallback

    if not graph_db.exists():
        print(f"error: graph.db not found (tried {graph_db})\n"
              f"       Provide --graph <path> or index the project with opencode-search first.",
              file=sys.stderr)
        return 1

    from ose_docgen.generate import generate

    result = generate(
        project_path=root,
        graph_db_path=graph_db,
        member_db_paths=args.members,
        docs_dir=args.docs_dir,
        llm=args.llm or None,
    )

    print(f"ose-docgen: {root.name} | sig={result['sig'][:8]}"
          f" | written={len(result['written'])} skipped={len(result['skipped'])}"
          f" errors={len(result['errors'])}")
    if result["errors"]:
        for e in result["errors"]:
            print(f"  ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
