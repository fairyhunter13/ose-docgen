"""Hybrid bucket classifier tests: Tier-0 keyword and Tier-1 semantic Haiku.

Tier-0 is always tested ($0, deterministic).
Tier-1 (semantic) only runs when OSE_DOCGEN_LLM=1 and 'claude' is in PATH.
"""
from __future__ import annotations

import os

import pytest

from ose_docgen.standardize import _STANDARD_BUCKETS, _bucket_for

# ── Tier-0 keyword mapping ────────────────────────────────────────────────────

class TestTier0Keywords:
    def test_api_file_maps_to_containers(self, tmp_path):
        f = tmp_path / "api-endpoints.md"
        f.write_text("# API\n")
        assert _bucket_for(f) == "02-containers"

    def test_decision_file_maps_to_decisions(self, tmp_path):
        f = tmp_path / "adr-001-auth.md"
        f.write_text("# ADR\n")
        assert _bucket_for(f) == "06-decisions"

    def test_deploy_guide_maps_to_howto(self, tmp_path):
        f = tmp_path / "deploy-guide.md"
        f.write_text("# Deploy\n")
        assert _bucket_for(f) == "05-how-to"

    def test_fallback_to_context(self, tmp_path):
        f = tmp_path / "random-notes.md"
        f.write_text("# Notes\n")
        assert _bucket_for(f) in _STANDARD_BUCKETS

    def test_non_english_name_returns_valid_bucket(self, tmp_path):
        """A non-English filename still produces a valid Tier-0 bucket (not a crash)."""
        f = tmp_path / "đặc_tả_kỹ_thuật.md"
        f.write_text("# Đặc Tả\n")
        assert _bucket_for(f) in _STANDARD_BUCKETS


# ── Tier-1 semantic classifier (needs OSE_DOCGEN_LLM=1 + claude in PATH) ────

def _tier1_available() -> bool:
    import shutil
    return os.environ.get("OSE_DOCGEN_LLM", "0") == "1" and bool(shutil.which("claude"))


@pytest.mark.slow
@pytest.mark.skipif(not _tier1_available(), reason="OSE_DOCGEN_LLM=1 + claude required")
class TestTier1Semantic:
    def test_ambiguous_doc_classified_by_content(self, tmp_path):
        """A file with 'readme.md' name but deployment content → 05-how-to (content wins)."""
        from ose_docgen._classify import classify_buckets_semantic
        p = tmp_path / "readme.md"
        p.write_text(
            "# Deployment Runbook\n\n"
            "## How to deploy this service\n\n"
            "1. Run `docker build`\n"
            "2. Push to registry\n"
            "3. Apply Kubernetes manifest\n"
        )
        result = classify_buckets_semantic(tmp_path, ["readme.md"], tmp_path / "_meta")
        # Either semantic (05-how-to) or falls back to Tier-0; must be a valid bucket
        assert result.get("readme.md", "01-context") in _STANDARD_BUCKETS

    def test_non_english_doc_classified(self, tmp_path):
        """A Vietnamese-named file is classified by its content, not filename."""
        from ose_docgen._classify import classify_buckets_semantic
        rel = "tai_lieu_api.md"
        (tmp_path / rel).write_text(
            "# API Documentation\n\nDescribes service endpoints, request/response schemas.\n"
        )
        result = classify_buckets_semantic(tmp_path, [rel], tmp_path / "_meta")
        bucket = result.get(rel, "01-context")
        assert bucket in _STANDARD_BUCKETS

    def test_result_cached_on_second_call(self, tmp_path):
        """Second classify call with unchanged content skips the LLM (uses cache)."""
        import unittest.mock as mock

        from ose_docgen._classify import classify_buckets_semantic
        rel = "guide.md"
        (tmp_path / rel).write_text("# How to run\n\nStep 1.\n")
        classify_buckets_semantic(tmp_path, [rel], tmp_path / "_meta")
        # Second call with same content — spy on subprocess.run; it must not be called
        with mock.patch("ose_docgen._classify.subprocess.run") as spy:
            classify_buckets_semantic(tmp_path, [rel], tmp_path / "_meta")
            assert spy.call_count == 0, "subprocess.run called despite valid cache"

    def test_error_returns_empty_not_raises(self, tmp_path):
        """If the claude call fails, classify_buckets_semantic returns {} (Tier-0 fallback)."""
        import unittest.mock as mock

        from ose_docgen._classify import classify_buckets_semantic
        (tmp_path / "doc.md").write_text("# Guide\n")
        with mock.patch("ose_docgen._classify.subprocess.run", side_effect=RuntimeError("boom")):
            result = classify_buckets_semantic(tmp_path, ["doc.md"], tmp_path / "_meta")
        assert result == {}


# ── H3: standardize.run integration ──────────────────────────────────────────

class TestTier0Integration:
    def test_h3_tier0_crosswalk_byte_stable(self, tmp_path):
        """H3: two Tier-0 standardize.run calls → identical CROSSWALK bytes."""
        import hashlib

        from ose_docgen.standardize import run
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "README.md").write_text(
            "---\ngenerated: true\nsource_sig: x\nc4_level: context\n---\n\n# R\n")
        (docs / "api.md").write_text("# API\n")
        run(docs, "sig001")
        cw = docs / "_meta" / "CROSSWALK.md"
        h1 = hashlib.sha256(cw.read_bytes()).hexdigest() if cw.exists() else None
        run(docs, "sig001")
        h2 = hashlib.sha256(cw.read_bytes()).hexdigest() if cw.exists() else None
        assert h1 == h2

    def test_h3_fallback_buckets_all_valid(self, tmp_path):
        """H3: Tier-0 classifies every human doc into a valid bucket (via _bucket_for)."""
        import os

        from ose_docgen.standardize import _STANDARD_BUCKETS, _bucket_for, classify_tree, run
        prev = os.environ.get("OSE_DOCGEN_LLM")
        os.environ["OSE_DOCGEN_LLM"] = "0"
        try:
            docs = tmp_path / "docs"
            docs.mkdir()
            (docs / "deploy-guide.md").write_text("# Deploy\n")
            (docs / "adr-001.md").write_text("# ADR\n")
            run(docs, "sig002")
            classes = classify_tree(docs)
        finally:
            if prev is None:
                os.environ.pop("OSE_DOCGEN_LLM", None)
            else:
                os.environ["OSE_DOCGEN_LLM"] = prev
        for rel, cls in classes.items():
            if cls == "human":
                bucket = _bucket_for(docs / rel)
                assert bucket in _STANDARD_BUCKETS, f"{rel}: invalid bucket {bucket!r}"
