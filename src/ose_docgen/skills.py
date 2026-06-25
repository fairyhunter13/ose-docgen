"""A6: detect recurring cross-member concerns → PDA SKILL.md files.

generate_skills(root, briefs, profile): identify concerns present in ≥2 repos
and write .claude/skills/<concern>/SKILL.md (PDA form). Human skills preserved.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ose_docgen.config import model_for_phase
from ose_docgen.provenance import classify, make_frontmatter
from ose_docgen.repo_explore import _from_json, run_claude_portal

_SKILLS_DIR = ".claude/skills"
_MAX_SKILLS = 8


def generate_skills(root: Path, briefs: list[dict], profile: str) -> list[str]:
    """Identify recurring concerns from briefs; write PDA SKILL.md files. Returns paths written."""
    safe = [{k: v for k, v in b.items() if not k.startswith("_")} for b in briefs]
    prompt = (
        f"Given these repo briefs, identify up to {_MAX_SKILLS} recurring cross-repo concerns "
        "(e.g. auth, observability, gRPC, db-migration, caching, CI-pipeline, error-handling). "
        "For each concern present in ≥2 repos, write a PDA-form SKILL.md with sections: "
        "# SKILL: <name>, ## When to use, ## Steps, ## Example. "
        "Output ONLY valid JSON: {\"skills\": [{\"name\": str, \"content\": str}]}. "
        "Never include /home/ paths or company/hostnames in content.\n\n"
        f"Briefs:\n{json.dumps(safe, indent=2)[:4000]}"
    )
    text = run_claude_portal(
        prompt, model_for_phase("skills"),
        add_dirs=[], tools="", profile=profile, cwd=str(root),
    )
    data = _from_json(text)
    if not data:
        return []

    written: list[str] = []
    skills_root = root / _SKILLS_DIR
    for skill in data.get("skills", [])[:_MAX_SKILLS]:
        name = re.sub(r"[^a-z0-9-]", "-", skill.get("name", "").lower()).strip("-")
        if not name:
            continue
        skill_file = skills_root / name / "SKILL.md"
        if skill_file.exists() and classify(skill_file) == "human":
            continue  # never overwrite human-authored skills
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        content = skill.get("content", "")
        if not content.startswith("---"):
            content = make_frontmatter("meta", "portal") + content
        skill_file.write_text(content, encoding="utf-8")
        written.append(str(skill_file.relative_to(root)))
    return written
