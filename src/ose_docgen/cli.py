"""Standalone CLI: ose-docgen [generate] <root> [--graph graph.db] [--docs-dir docs/] [--llm]
                  ose-docgen clean <root> [--docs-dir docs/]

Usable outside the OSE daemon — runs Phase 1 + optional Phase 2 on any indexed project.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_generate(argv: list[str]) -> int:
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
            graph_db = root / "graph.db"

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


def _cmd_clean(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="ose-docgen clean",
        description="Remove generated docs from a repository, preserving human files.",
    )
    p.add_argument("root", help="Repository root path")
    p.add_argument("--docs-dir", default=None,
                   help="Docs directory to clean (default: <root>/docs/)")
    args = p.parse_args(argv)

    root = Path(args.root).resolve()
    docs_dir = Path(args.docs_dir).resolve() if args.docs_dir else root / "docs"

    from ose_docgen.cleanup import clean_generated

    result = clean_generated(docs_dir)
    print(f"ose-docgen clean: removed={len(result['removed'])} "
          f"preserved={len(result['preserved'])} pruned_dirs={len(result['pruned_dirs'])}")
    return 0


def _cmd_portal(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        prog="ose-docgen portal",
        description="Agentic repo-native portal (OSE-independent, reads real filesystem).",
    )
    p.add_argument("root", help="Repository root path")
    p.add_argument("--member", action="append", default=None, dest="members",
                   help="Additional member paths (repeatable; auto-discovered if omitted)")
    p.add_argument("--skills", action="store_true",
                   help="Generate .claude/skills/ stubs for recurring cross-repo concerns")
    p.add_argument("--no-llm", action="store_true",
                   help="Skip all LLM calls (dry-run)")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 1
    from ose_docgen.portal import portal
    result = portal(root, member_paths=args.members, skills=args.skills, no_llm=args.no_llm)
    written = result.get("written", [])
    errors = result.get("errors", [])
    mode = result.get("mode", "portal")
    print(f"ose-docgen portal: {root.name} | written={len(written)} "
          f"errors={len(errors)} mode={mode}")
    if result.get("verify"):
        vr = result["verify"]
        print(f"  truthfulness: {vr['score']:.2%} "
              f"({vr['valid_refs']}/{vr['total_refs']} refs valid)")
    for e in errors:
        print(f"  ERROR: {e}", file=sys.stderr)
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    args_raw = list(argv) if argv is not None else sys.argv[1:]
    if args_raw and args_raw[0] == "clean":
        return _cmd_clean(args_raw[1:])
    if args_raw and args_raw[0] == "portal":
        return _cmd_portal(args_raw[1:])
    return _cmd_generate(args_raw)


if __name__ == "__main__":
    raise SystemExit(main())
