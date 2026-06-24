"""Provenance management: per-file frontmatter + provenance.json + human-file guard.

Every file written by the tool carries:
  generated: true
  source_sig: <sha1 of source graph.db mtime fingerprint>
  hier_version: fg1+lp2
  c4_level: context|container|component|code|meta

Any file missing the marker OR with generated: false is human-authored → never touched.
Idempotency: if source_sig has not changed, skip regeneration (no diff produced).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_GEN_RE = re.compile(r"^generated:\s*(true|false)", re.MULTILINE)
_SIG_RE = re.compile(r"^source_sig:\s*(\S+)", re.MULTILINE)

HIER_VERSION = "fg1+lp2"


def _parse_fm(text: str) -> dict[str, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}
    result: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ": " in line:
            k, _, v = line.partition(": ")
            result[k.strip()] = v.strip()
    return result


def is_generated(path: Path) -> bool:
    """True iff this file has generated: true frontmatter (tool-owned)."""
    if not path.exists():
        return False
    fm = _parse_fm(path.read_text(encoding="utf-8"))
    return fm.get("generated", "false").lower() == "true"


def source_sig(path: Path) -> str | None:
    """Return the source_sig stored in a generated file's frontmatter."""
    if not path.exists():
        return None
    fm = _parse_fm(path.read_text(encoding="utf-8"))
    return fm.get("source_sig")


def make_frontmatter(c4_level: str, sig: str) -> str:
    """Build a YAML frontmatter block for a generated file."""
    return f"---\ngenerated: true\nsource_sig: {sig}\nhier_version: {HIER_VERSION}\nc4_level: {c4_level}\n---\n\n"


def compute_sig(graph_db: Path) -> str:
    """Compute a short content-signature for a graph.db (mtime + size)."""
    stat = graph_db.stat()
    raw = f"{graph_db}:{stat.st_mtime_ns}:{stat.st_size}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def needs_regen(path: Path, sig: str) -> bool:
    """True if the file should be regenerated (new, not generated, or source_sig drifted)."""
    if not path.exists():
        return True
    if not is_generated(path):
        return False  # human-authored — never regenerate
    return source_sig(path) != sig


def write_generated(path: Path, c4_level: str, sig: str, body: str) -> None:
    """Write a generated file with provenance frontmatter. Parent dir created if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(make_frontmatter(c4_level, sig) + body, encoding="utf-8")


def load_provenance(meta_dir: Path) -> dict:
    p = meta_dir / "provenance.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_provenance(meta_dir: Path, data: dict) -> None:
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "provenance.json").write_text(
        json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
    )
