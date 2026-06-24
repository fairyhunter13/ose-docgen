"""Phase 3 tests: migration model — classify, CROSSWALK, MIGRATION.md, idempotency.

Uses real graph.db. No Claude calls. No GPU required.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ose_docgen.generate import generate
from ose_docgen.provenance import classify, is_generated, make_frontmatter

_GRAPH_DB = Path("/home/hafiz/.local/share/opencode-search/indexes/"
                 "astro-api-customer-spring-00318666f4ef488b/graph.db")
_PROJECT = Path("/tmp/ose-docgen-test-project")


@pytest.fixture(autouse=True)
def _project_dir():
    _PROJECT.mkdir(exist_ok=True)


@pytest.fixture
def real_graph_db():
    if not _GRAPH_DB.exists():
        pytest.skip(f"graph.db not found: {_GRAPH_DB}")
    return _GRAPH_DB


def _run(graph_db: Path, docs_dir: Path) -> dict:
    return generate(
        project_path=_PROJECT, graph_db_path=graph_db, docs_dir=str(docs_dir), llm=False
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
    def test_crosswalk_built(self, real_graph_db, tmp_path):
        human = tmp_path / "repository-guide.md"
        human.write_text("# My Guide\n", encoding="utf-8")
        _run(real_graph_db, tmp_path)
        crosswalk = tmp_path / "_meta" / "CROSSWALK.md"
        assert crosswalk.exists(), "CROSSWALK.md must be generated"
        assert is_generated(crosswalk)
        assert "repository-guide.md" in crosswalk.read_text(encoding="utf-8")

    def test_crosswalk_human_bucket_assignment(self, real_graph_db, tmp_path):
        (tmp_path / "api-endpoints.md").write_text("# API\n", encoding="utf-8")
        _run(real_graph_db, tmp_path)
        content = (tmp_path / "_meta" / "CROSSWALK.md").read_text(encoding="utf-8")
        assert "02-containers" in content or "04-reference" in content

    def test_no_human_files_gives_empty_crosswalk(self, real_graph_db, tmp_path):
        _run(real_graph_db, tmp_path)
        cw = tmp_path / "_meta" / "CROSSWALK.md"
        assert cw.exists()
        assert "No human-authored files found" in cw.read_text(encoding="utf-8")


class TestHumanPreservation:
    def test_human_file_byte_unchanged(self, real_graph_db, tmp_path):
        human = tmp_path / "DESIGN.md"
        human.write_text("# My Design\nImportant notes.\n")
        before = hashlib.sha256(human.read_bytes()).hexdigest()
        _run(real_graph_db, tmp_path)
        assert hashlib.sha256(human.read_bytes()).hexdigest() == before

    def test_asset_file_not_modified(self, real_graph_db, tmp_path):
        asset = tmp_path / "logo.png"
        asset.write_bytes(b"\x89PNG\r\n\x1a\n")
        before = asset.read_bytes()
        _run(real_graph_db, tmp_path)
        assert asset.read_bytes() == before, "asset file was modified"


class TestMigrationMd:
    def test_migration_md_emitted(self, real_graph_db, tmp_path):
        _run(real_graph_db, tmp_path)
        assert (tmp_path / "_meta" / "MIGRATION.md").exists()

    def test_migration_md_shows_human_count(self, real_graph_db, tmp_path):
        (tmp_path / "guide.md").write_text("# Guide\n")
        _run(real_graph_db, tmp_path)
        content = (tmp_path / "_meta" / "MIGRATION.md").read_text(encoding="utf-8")
        assert "HUMAN-PROSE" in content
        assert "1" in content  # at least one human file counted

    def test_migration_md_shows_asset_skipped(self, real_graph_db, tmp_path):
        (tmp_path / "fig.png").write_bytes(b"\x89PNG")
        _run(real_graph_db, tmp_path)
        content = (tmp_path / "_meta" / "MIGRATION.md").read_text(encoding="utf-8")
        assert "NON-DOC ASSET" in content


class TestMigrationIdempotency:
    def test_second_run_does_not_rewrite_crosswalk(self, real_graph_db, tmp_path):
        (tmp_path / "notes.md").write_text("# Notes\n")
        _run(real_graph_db, tmp_path)
        cw = tmp_path / "_meta" / "CROSSWALK.md"
        mtime1 = cw.stat().st_mtime_ns
        _run(real_graph_db, tmp_path)
        assert cw.stat().st_mtime_ns == mtime1, "CROSSWALK.md was rewritten on second run"
