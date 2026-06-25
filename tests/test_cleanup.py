"""CT1/CT2: clean_generated() unit tests — no OSE, no GPU, no network."""
from __future__ import annotations

from pathlib import Path

_GEN_FM = (
    "---\ngenerated: true\nsource_sig: abc123\n"
    "hier_version: fg1+lp2\nc4_level: context\n---\n\n"
)


def _seed(docs: Path, *, human: bool = False, asset: bool = False) -> None:
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "_meta").mkdir()
    (docs / "_meta" / "provenance.json").write_text("{}")
    (docs / "README.md").write_text(_GEN_FM + "# Generated\n")
    sub = docs / "01-context"
    sub.mkdir()
    (sub / "ctx.md").write_text(_GEN_FM + "# Ctx\n")
    if human:
        (docs / "MANUAL.md").write_text("# Human\n")
    if asset:
        (docs / "logo.png").write_bytes(b"\x89PNG\r\n")


def test_ct1_mixed_generated_preserved(tmp_path):
    """CT1: generated + _meta/ removed; human byte-identical; asset kept; second run no-op."""
    from ose_docgen.cleanup import clean_generated

    docs = tmp_path / "docs"
    _seed(docs, human=True, asset=True)
    human_bytes = (docs / "MANUAL.md").read_bytes()

    r = clean_generated(docs)

    assert "README.md" in r["removed"]
    assert "_meta/provenance.json" in r["removed"]
    assert not (docs / "README.md").exists()
    assert not (docs / "_meta").exists()
    assert (docs / "MANUAL.md").read_bytes() == human_bytes, "human file must be byte-identical"
    assert "MANUAL.md" in r["preserved"]
    assert (docs / "logo.png").exists(), "asset must survive"

    # Second run: no marker left, nothing to remove
    r2 = clean_generated(docs)
    assert r2["removed"] == []


def test_ct2_all_generated_removes_dir(tmp_path):
    """CT2: all-generated docs/ → directory removed entirely; idempotent on missing dir."""
    from ose_docgen.cleanup import clean_generated

    docs = tmp_path / "docs"
    _seed(docs)

    r = clean_generated(docs)

    assert r["removed"]
    assert not docs.exists(), "all-generated docs/ must be fully removed"
    assert "." in r["pruned_dirs"]

    r2 = clean_generated(docs)
    assert r2 == {"removed": [], "preserved": [], "pruned_dirs": []}
