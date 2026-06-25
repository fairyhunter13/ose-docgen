"""Phase 1 tests: deterministic skeleton, idempotency, human-file preservation, path-leak guard.

Uses synth_graph_db (sqlite3 fixture — no OSE import, no GPU, always runnable).
Does NOT call Claude Code (OSE_DOCGEN_LLM defaults to 0).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from ose_docgen.generate import generate
from ose_docgen.provenance import is_generated, source_sig


def run(graph_db: Path, docs_dir: str, project_path: Path, **kw) -> dict:
    return generate(project_path=project_path, graph_db_path=graph_db, docs_dir=docs_dir, **kw)


class TestDeterministicSkeleton:
    def test_generates_expected_sections(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        result = run(synth_graph_db, str(tmp_path / "docs"), project)
        written = [Path(p).name for p in result["written"]]
        assert "README.md" in written
        assert result["errors"] == []
        assert len(result["written"]) > 5

    def test_no_claude_invocation(self, synth_graph_db, tmp_path, monkeypatch):
        """Phase 1 (llm=False) must not call claude binary."""
        import subprocess as sp
        calls: list = []
        original = sp.run
        def patched_run(cmd, **kw):
            if "claude" in str(cmd):
                calls.append(cmd)
            return original(cmd, **kw)
        monkeypatch.setattr(sp, "run", patched_run)
        project = tmp_path / "project"
        project.mkdir()
        run(synth_graph_db, str(tmp_path / "docs"), project)
        assert calls == [], f"claude was invoked: {calls}"


class TestIdempotency:
    def test_second_run_skips_all(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = str(tmp_path / "docs")
        r1 = run(synth_graph_db, docs, project)
        r2 = run(synth_graph_db, docs, project)
        assert len(r2["written"]) == 0, "second run should skip all unmodified files"
        assert len(r2["skipped"]) == len(r1["written"]) + len(r1["skipped"])

    def test_source_sig_in_frontmatter(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        run(synth_graph_db, str(docs), project)
        readme = docs / "README.md"
        assert readme.exists()
        assert is_generated(readme)
        sig = source_sig(readme)
        assert sig is not None and len(sig) > 8


class TestHumanFilePreservation:
    def test_human_readme_not_overwritten(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        human = docs / "README.md"
        human.write_text("# My hand-authored docs\nImportant content.\n")
        before_hash = hashlib.sha256(human.read_bytes()).hexdigest()
        run(synth_graph_db, str(docs), project)
        assert human.read_bytes().__len__() > 0
        assert hashlib.sha256(human.read_bytes()).hexdigest() == before_hash, \
            "human-authored README was modified"

    def test_human_file_not_is_generated(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        human = docs / "README.md"
        human.write_text("# Hand-authored\n")
        assert not is_generated(human)
        run(synth_graph_db, str(docs), project)
        assert not is_generated(human), "is_generated() flipped on human file"


class TestPathLeakGuard:
    def test_no_absolute_device_paths_in_output(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        run(synth_graph_db, str(docs), project)
        home = str(Path.home())
        violations: list[str] = []
        for md_file in docs.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            if home in content:
                violations.append(str(md_file))
        assert not violations, f"Absolute device paths leaked in: {violations}"


class TestNoDeepSeekInTool:
    def test_no_deepseek_import(self):
        """Source guard: the docgen tool must never import or reference deepseek."""
        src_dir = Path(__file__).parent.parent / "src" / "ose_docgen"
        violations: list[str] = []
        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            if "deepseek" in content.lower():
                violations.append(str(py_file))
        assert not violations, f"DeepSeek references found in tool source: {violations}"

    def test_no_anthropic_api_key_in_subprocess_env(self):
        """Subprocess env must not contain ANTHROPIC_API_KEY (subscription-only)."""
        import os
        os.environ["ANTHROPIC_API_KEY"] = "test-sentinel-key"
        from ose_docgen.accounts import subprocess_env
        env = subprocess_env("/tmp/fake-profile")
        assert "ANTHROPIC_API_KEY" not in env, \
            "ANTHROPIC_API_KEY leaked into subprocess env — would trigger API billing"
        del os.environ["ANTHROPIC_API_KEY"]
