"""Repo-native agentic IH portal: explore → architect → write → cite-gate → verify."""
from __future__ import annotations

import json
from pathlib import Path

from ose_docgen import config
from ose_docgen.accounts import pick_profile
from ose_docgen.cite_gate import check_citations
from ose_docgen.config import CLAUDE_PROFILES, MAX_PAGES_PER_RUN, model_for_phase
from ose_docgen.provenance import classify, needs_regen, save_provenance, write_generated
from ose_docgen.repo_explore import (
    _from_json, discover_members, explore_repo, portal_sig, run_claude_portal,
)

_TIMEOUT_ARCH = 180
_TIMEOUT_WRITE = 120


def portal(root, *, docs_dir=None, member_paths=None, skills=False, no_llm=False, max_pages=None):
    root = Path(root).resolve()
    if docs_dir is None:
        docs_dir = root / config.DOCS_DIR
    ih_dir = Path(docs_dir) / "information-hierarchy"
    human = _snapshot_human(ih_dir)
    members = [Path(m).resolve() for m in (member_paths or [])] or discover_members(root)

    if no_llm:
        return {"written": [], "skipped": [], "errors": [], "mode": "no_llm"}

    valid_profiles = [p for p in CLAUDE_PROFILES if (Path(p) / ".credentials.json").exists()]
    profile = pick_profile(valid_profiles)
    if not profile and valid_profiles:
        profile = valid_profiles[0]
    if not profile:
        return {"written": [], "skipped": [], "errors": ["no_profile"], "mode": "ih"}

    sig = portal_sig(root)
    briefs = [explore_repo(r, profile=profile) for r in [root, *members]]
    plan = _architect(briefs, profile)
    # Profile failover: if architect fails, try remaining valid profiles
    if not plan:
        for alt in [p for p in valid_profiles if p != profile]:
            alt_briefs = [explore_repo(r, profile=alt) for r in [root, *members]]
            plan = _architect(alt_briefs, alt)
            if plan:
                profile = alt
                briefs = alt_briefs
                break
    if not plan:
        _restore_human(human)
        return {"written": [], "skipped": [], "errors": ["architect_failed"], "mode": "ih"}

    meta_dir = ih_dir / "_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "ih_plan.json").write_text(json.dumps(plan, indent=2))
    written, errors = _write_pages(plan, ih_dir, root, members, sig, profile, max_pages=max_pages)

    from ose_docgen.verify import verify
    vr = verify(ih_dir, root, plan, members=members)
    if vr["dead_refs"]:
        (meta_dir / "VALIDITY.md").write_text(
            f"# VALIDITY\nTruthfulness: {vr['score']:.2%}\n\n## Dead references\n"
            + "\n".join(f"- {d}" for d in vr["dead_refs"])
        )
    _restore_human(human)
    save_provenance(meta_dir, {"sig": sig, "mode": "ih", "written": len(written), "truthfulness": vr["score"]})
    return {"written": written, "skipped": [], "errors": errors, "sig": sig, "verify": vr, "mode": "ih"}


def _snapshot_human(ih_dir):
    if not ih_dir.exists():
        return {}
    return {str(p): p.read_bytes() for p in ih_dir.rglob("*") if p.is_file() and classify(p) == "human"}


def _restore_human(human):
    for s, b in human.items():
        p = Path(s)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)


def _architect(briefs, profile):
    safe = [{k: v for k, v in b.items() if not k.startswith("_")} for b in briefs]
    prompt = (
        "You are a software architect. Design an Information Hierarchy (IH) for these repos. "
        "An IH is a value/generality spine: Primary (broadest concepts) -> Secondary -> Tertiary (most specific). "
        f"Output ONLY valid JSON with key 'pages' (list of up to {MAX_PAGES_PER_RUN} objects). "
        "Each page: 'path' (relative to information-hierarchy/), 'title', "
        "'ih_level' ('Primary'|'Secondary'|'Tertiary'), "
        "'grounding_sources' (up to 5 repo-relative paths), 'cross_links' (list of page paths). "
        "Required: 'index.md' (system-wide IH spine). "
        "Page filenames must be semantic domain terms (e.g. 'search-pipeline.md'), never numeric sequences. "
        "No /home/ or absolute paths in any field.\n\n"
        f"Repo briefs:\n{json.dumps(safe, indent=2)[:6000]}"
    )
    text = run_claude_portal(prompt, model_for_phase("architect"),
                              add_dirs=[], tools="", profile=profile, timeout=_TIMEOUT_ARCH)
    return _from_json(text)


def _write_pages(plan, ih_dir, root, members, sig, profile, max_pages=None):
    limit = max_pages if max_pages is not None else MAX_PAGES_PER_RUN
    pages = sorted(plan.get("pages", []), key=lambda p: p.get("path", "").count("/"))
    add_dirs = [str(root), *[str(m) for m in members]]
    written, errors = [], []
    for pg in pages[:limit]:
        rel = pg.get("path", "")
        if not rel:
            continue
        dest = ih_dir / rel
        if not needs_regen(dest, sig):
            continue
        srcs = ", ".join(pg.get("grounding_sources", [])[:5]) or "repo overview"
        ih_level = pg.get("ih_level", "Secondary")
        prompt = (
            f"Write the IH page '{pg.get('title', '')}' (level: {ih_level}) "
            f"at information-hierarchy/{rel}. "
            "5-section canonical IH order:\n"
            "S1 [Topic] Hierarchy -- PRIMARY/SECONDARY/TERTIARY generality tree\n"
            "S2 Traversal: drill-down / roll-up\n"
            "S3 Visual ranking\n"
            "S4 Supporting IA systems (labeling/navigation/search -- one heading)\n"
            "S5 Cross-references\n\n"
            "CRITICAL: Every code claim must carry [code: file:line] you actually verified. "
            f"Ground in: {srcs}. Output ONLY markdown body. No frontmatter. No /home/ paths."
        )
        text = run_claude_portal(prompt, model_for_phase("write"), add_dirs=add_dirs,
                                  tools="Read", profile=profile, timeout=_TIMEOUT_WRITE, cwd=str(root))
        if not text or not text.strip():
            errors.append(f"{rel}:empty_response")
            continue
        cite_errors = check_citations(text, root)
        if cite_errors:
            errors.append(f"{rel}:citation_failed:" + "; ".join(cite_errors[:3]))
            continue
        write_generated(dest, ih_level.lower(), sig, text.strip())
        written.append(rel)
    return written, errors
