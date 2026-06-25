"""Phase 3 tests: migration model — classify, CROSSWALK, MIGRATION.md, idempotency.

Uses synth_graph_db (sqlite3 fixture — no OSE import, no GPU, always runnable).
No Claude calls. No GPU required.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from ose_docgen.generate import generate
from ose_docgen.provenance import classify, is_generated, make_frontmatter


def _run(graph_db: Path, docs_dir: Path, project_path: Path) -> dict:
    return generate(
        project_path=project_path, graph_db_path=graph_db, docs_dir=str(docs_dir), llm=False
    )


class TestClassify:
    def test_classify_generated(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(make_frontmatter("meta", "abc123") + "body\n", encoding="utf-8")
        assert classify(f) == "generated"

    def test_classify_human(self, tmp_path):
        f = tmp_path / "README.md"
        f.write_text("# Hand-authored\n", encoding="utf-8")
        assert classify(f) == "human"

    def test_classify_asset(self, tmp_path):
        f = tmp_path / "logo.png"
        f.write_bytes(b"\x89PNG\r\n")
        assert classify(f) == "asset"

    def test_classify_json_as_asset(self, tmp_path):
        f = tmp_path / "config.json"
        f.write_text('{"key": 1}', encoding="utf-8")
        assert classify(f) == "asset"


class TestCrossWalk:
    def test_crosswalk_built(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        human = docs / "repository-guide.md"
        human.write_text("# My Guide\n", encoding="utf-8")
        _run(synth_graph_db, docs, project)
        crosswalk = docs / "_meta" / "CROSSWALK.md"
        assert crosswalk.exists(), "CROSSWALK.md must be generated"
        assert is_generated(crosswalk)
        assert "repository-guide.md" in crosswalk.read_text(encoding="utf-8")

    def test_crosswalk_human_bucket_assignment(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "api-endpoints.md").write_text("# API\n", encoding="utf-8")
        _run(synth_graph_db, docs, project)
        content = (docs / "_meta" / "CROSSWALK.md").read_text(encoding="utf-8")
        assert "02-containers" in content or "04-reference" in content

    def test_no_human_files_gives_empty_crosswalk(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        _run(synth_graph_db, docs, project)
        cw = docs / "_meta" / "CROSSWALK.md"
        assert cw.exists()
        assert "No human-authored files found" in cw.read_text(encoding="utf-8")


class TestHumanPreservation:
    def test_human_file_byte_unchanged(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        human = docs / "DESIGN.md"
        human.write_text("# My Design\nImportant notes.\n")
        before = hashlib.sha256(human.read_bytes()).hexdigest()
        _run(synth_graph_db, docs, project)
        assert hashlib.sha256(human.read_bytes()).hexdigest() == before

    def test_asset_file_not_modified(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        asset = docs / "logo.png"
        asset.write_bytes(b"\x89PNG\r\n\x1a\n")
        before = asset.read_bytes()
        _run(synth_graph_db, docs, project)
        assert asset.read_bytes() == before, "asset file was modified"


class TestMigrationMd:
    def test_migration_md_emitted(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        _run(synth_graph_db, docs, project)
        assert (docs / "_meta" / "MIGRATION.md").exists()

    def test_migration_md_shows_human_count(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("# Guide\n")
        _run(synth_graph_db, docs, project)
        content = (docs / "_meta" / "MIGRATION.md").read_text(encoding="utf-8")
        assert "HUMAN-PROSE" in content
        assert "1" in content  # at least one human file counted

    def test_migration_md_shows_asset_skipped(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "fig.png").write_bytes(b"\x89PNG")
        _run(synth_graph_db, docs, project)
        content = (docs / "_meta" / "MIGRATION.md").read_text(encoding="utf-8")
        assert "NON-DOC ASSET" in content


class TestMigrationIdempotency:
    def test_second_run_does_not_rewrite_crosswalk(self, synth_graph_db, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "notes.md").write_text("# Notes\n")
        _run(synth_graph_db, docs, project)
        cw = docs / "_meta" / "CROSSWALK.md"
        mtime1 = cw.stat().st_mtime_ns
        _run(synth_graph_db, docs, project)
        assert cw.stat().st_mtime_ns == mtime1, "CROSSWALK.md was rewritten on second run"
