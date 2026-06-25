"""Phase 4 portal tests (A): agentic portal on synthetic root + symlinked member.

PE1 requires real claude -p (marked slow). No GPU. Subscription required.
PE1a: portal generates structure + preserves human + no /home/ leak.
PE1b: second run is idempotent (0 new writes).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_MEMBER_CANDIDATE = Path("/home/hafiz/go/src/github.com/astronautsid/astro-boilerplate")
_SYNTH_ROOT = Path("/tmp/ose-portal-synth-pe1")


def _build_synth(root: Path) -> None:
    root.mkdir(exist_ok=True)
    (root / "main.go").write_text("package main\n\nfunc main() {}\n")
    (root / "go.mod").write_text("module example.com/portal-test\n\ngo 1.21\n")
    db = root / "db" / "migrations"
    db.mkdir(parents=True, exist_ok=True)
    (db / "001_create_users.sql").write_text("CREATE TABLE users (id SERIAL PRIMARY KEY);\n")
    ci = root / ".github" / "workflows"
    ci.mkdir(parents=True, exist_ok=True)
    (ci / "ci.yml").write_text(
        "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/checkout@v4\n"
    )
    # Symlinked member (skip if real repo absent)
    link = root / "member-service"
    if _MEMBER_CANDIDATE.exists() and not link.exists():
        link.symlink_to(_MEMBER_CANDIDATE)
    # Pre-seeded human file — must survive
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "human-guide.md").write_text("# Human Guide\n\nThis file is human-authored.\n")


@pytest.fixture(scope="module")
def synth_root():
    _build_synth(_SYNTH_ROOT)
    yield _SYNTH_ROOT


@pytest.mark.slow
def test_pe1a_portal_generates_structure(synth_root):
    """PE1a: portal writes docs/, preserves human file, no /home/ leak."""
    from ose_docgen.portal import portal

    member = synth_root / "member-service"
    member_paths = [str(member.resolve())] if member.exists() else None

    result = portal(str(synth_root), member_paths=member_paths, skills=False)
    assert isinstance(result.get("written"), list)

    docs = synth_root / "docs"
    assert docs.exists(), "docs/ must be created by portal"

    # Human file must survive
    human = docs / "human-guide.md"
    assert human.exists(), "human-guide.md must be preserved"
    assert "human-authored" in human.read_text(), "human file content must be byte-identical"

    # Provenance recorded
    prov_file = docs / "_meta" / "provenance.json"
    assert prov_file.exists(), "_meta/provenance.json must exist"
    prov = json.loads(prov_file.read_text())
    assert prov.get("mode") == "portal"

    # No /home/ leaks in any generated page
    for md in docs.rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="replace")
        assert "/home/" not in text, f"/home/ path leaked in {md.relative_to(docs)}"

    # Truthfulness score present
    if result.get("verify"):
        score = result["verify"]["score"]
        assert score >= 0.70, f"truthfulness {score:.2%} below acceptable minimum"

    # Hierarchy plan was written
    plan_file = docs / "_meta" / "hierarchy_plan.json"
    assert plan_file.exists(), "hierarchy_plan.json must exist"
    plan = json.loads(plan_file.read_text())
    assert "pages" in plan, "hierarchy_plan.json must have 'pages' key"
    assert len(plan["pages"]) > 0, "plan must contain at least one page"


@pytest.mark.slow
def test_pe1b_portal_idempotent(synth_root):
    """PE1b: second portal run produces 0 new writes (idempotent)."""
    from ose_docgen.portal import portal

    member = synth_root / "member-service"
    member_paths = [str(member.resolve())] if member.exists() else None

    result = portal(str(synth_root), member_paths=member_paths, skills=False)
    assert result.get("written", []) == [], (
        f"second portal run must write 0 new pages; got {result['written']}"
    )
    # Human file still intact
    human = synth_root / "docs" / "human-guide.md"
    assert human.exists() and "human-authored" in human.read_text()
