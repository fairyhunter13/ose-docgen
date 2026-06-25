"""Repo-native agentic portal: explore → architect → write → verify → skills.

OSE-independent — reads real filesystem, not graph.db. Writes only at root/docs/ (HR27).
Pipeline: A2 explore (Haiku) → A3 architect (Sonnet) → A4 write (Haiku, topological)
          → A5 verify → A6 skills (opt-in) → standardize.
"""
from __future__ import annotations

import json
from pathlib import Path

from ose_docgen import config, standardize
from ose_docgen.accounts import pick_profile
from ose_docgen.config import CLAUDE_PROFILES, MAX_PAGES_PER_RUN, model_for_phase
from ose_docgen.provenance import classify, needs_regen, save_provenance, write_generated
from ose_docgen.repo_explore import (
    _from_json,
    discover_members,
    explore_repo,
    portal_sig,
    run_claude_portal,
)

_TIMEOUT_ARCH = 180
_TIMEOUT_WRITE = 120


def portal(
    root: str | Path, *,
    member_paths: list[str] | None = None,
    skills: bool = False,
    no_llm: bool = False,
) -> dict:
    """Run the agentic portal on root. Returns result dict."""
    root = Path(root).resolve()
    docs_dir = root / config.DOCS_DIR
    human = _snapshot_human(docs_dir)
    members = [Path(m).resolve() for m in (member_paths or [])] or discover_members(root)

    if no_llm:
        return {"written": [], "skipped": [], "errors": [], "mode": "no_llm"}

    profile = pick_profile(CLAUDE_PROFILES)
    if not profile:
        return {"written": [], "skipped": [], "errors": ["no_profile"]}

    sig = portal_sig(root)
    briefs = [explore_repo(r, profile=profile) for r in [root, *members]]

    plan = _architect(briefs, profile)
    if not plan:
        _restore_human(human)
        return {"written": [], "skipped": [], "errors": ["architect_failed"]}

    meta_dir = docs_dir / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "hierarchy_plan.json").write_text(json.dumps(plan, indent=2))

    written, errors = _write_pages(plan, docs_dir, root, members, sig, profile)

    from ose_docgen.verify import verify
    vr = verify(docs_dir, root, plan)
    dead_section = (
        "\n## Dead references\n" + "\n".join(f"- {d}" for d in vr["dead_refs"])
        if vr["dead_refs"] else ""
    )
    (meta_dir / "VALIDITY.md").write_text(
        f"# VALIDITY\nTruthfulness: {vr['score']:.2%}\n{dead_section}"
    )

    if skills:
        from ose_docgen.skills import generate_skills
        generate_skills(root, briefs, profile)

    _restore_human(human)
    standardize.run(docs_dir, sig)
    save_provenance(meta_dir, {
        "sig": sig, "mode": "portal",
        "written": len(written), "truthfulness": vr["score"],
    })
    return {"written": written, "skipped": [], "errors": errors, "sig": sig, "verify": vr}


def _snapshot_human(docs_dir: Path) -> dict[str, bytes]:
    if not docs_dir.exists():
        return {}
    return {
        str(p): p.read_bytes()
        for p in docs_dir.rglob("*")
        if p.is_file() and classify(p) == "human"
    }


def _restore_human(human: dict[str, bytes]) -> None:
    for s, b in human.items():
        p = Path(s)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)


def _architect(briefs: list[dict], profile: str) -> dict | None:
    safe = [{k: v for k, v in b.items() if not k.startswith("_")} for b in briefs]
    prompt = (
        "You are a software architect. Design a C4+Diátaxis documentation hierarchy "
        "for these repos. "
        f"Output ONLY valid JSON with key 'pages' (list of ≤{MAX_PAGES_PER_RUN} objects). "
        "Each page: path (relative to docs/), title, c4_level "
        "(context|container|component|code|meta), grounding_sources (list of repo-relative "
        "file paths that ground this page), cross_links (list of page paths). "
        "Required pages: 00_PORTAL/index.md, 00_SYSTEM_MAP/index.md, "
        "01-context/system-context.md, containers under 02-containers/, "
        "domain components under 03-components/, 04-reference/, 05-howto/, 06-decisions/. "
        "Paths must be root-relative — never include /home/ or absolute paths.\n\n"
        f"Repo briefs:\n{json.dumps(safe, indent=2)[:6000]}"
    )
    text = run_claude_portal(prompt, model_for_phase("architect"),
                              add_dirs=[], tools="", profile=profile, timeout=_TIMEOUT_ARCH)
    return _from_json(text)


def _write_pages(
    plan: dict, docs_dir: Path, root: Path,
    members: list[Path], sig: str, profile: str,
) -> tuple[list[str], list[str]]:
    pages = sorted(plan.get("pages", []), key=lambda p: p.get("path", "").count("/"))
    add_dirs = [str(root), *[str(m) for m in members]]
    written: list[str] = []
    errors: list[str] = []
    for pg in pages[:MAX_PAGES_PER_RUN]:
        rel = pg.get("path", "")
        if not rel:
            continue
        dest = docs_dir / rel
        if not needs_regen(dest, sig):
            continue
        srcs = ", ".join(pg.get("grounding_sources", [])[:5]) or "repo overview"
        prompt = (
            f"Output ONLY the markdown body (no frontmatter, no explanation) for the "
            f"'{pg.get('title', '')}' documentation page. "
            f"Ground it in: {srcs}. Concise, factual, source-verified. "
            "No /home/ paths or internal hostnames. "
            "Start directly with a heading — no preamble."
        )
        text = run_claude_portal(
            prompt, model_for_phase("write"),
            add_dirs=add_dirs, tools="Read,Bash",
            profile=profile, timeout=_TIMEOUT_WRITE, cwd=str(root),
        )
        if text and text.strip():
            write_generated(dest, pg.get("c4_level", "meta"), sig, text.strip())
            written.append(rel)
        else:
            errors.append(f"{rel}:empty_response")
    return written, errors
