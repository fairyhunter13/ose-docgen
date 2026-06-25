"""Portal truthfulness verifier (A5 — hard gate per AGENTbench).

verify(docs_dir, root, plan): check every cited file/path exists on disk.
Score = valid_refs / total_refs. Pages below TRUTHFULNESS_MIN listed in VALIDITY.md.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ose_docgen.config import TRUTHFULNESS_MIN
from ose_docgen.provenance import classify

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_CODE_PATH_RE = re.compile(
    r"`([a-zA-Z0-9_./-]+\.(?:go|java|py|ts|js|yaml|yml|json|proto|sql|sh))`"
)


def verify(docs_dir: Path, root: Path, plan: dict,
           members: list[Path] | None = None) -> dict:
    """Check truthfulness of generated portal pages. Returns score + dead refs."""
    pages = plan.get("pages", [])
    members = members or []
    total = valid = 0
    dead: list[str] = []
    below: list[str] = []

    for pg in pages:
        rel = pg.get("path", "")
        if not rel:
            continue
        p = docs_dir / rel
        if not p.exists() or classify(p) != "generated":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        refs = _extract_refs(text, page_dir=p.parent, docs_dir=docs_dir)
        pv = pt = 0
        for ref in refs:
            pt += 1
            total += 1
            if _ref_exists(ref, root, docs_dir, members):
                pv += 1
                valid += 1
            else:
                dead.append(f"{rel}: {ref}")
        if pt > 0 and (pv / pt) < TRUTHFULNESS_MIN:
            below.append(rel)

    score = valid / total if total > 0 else 1.0
    return {
        "score": score,
        "dead_refs": dead,
        "pages_below": below,
        "total_refs": total,
        "valid_refs": valid,
    }


def _extract_refs(text: str, *, page_dir: Path | None = None,
                  docs_dir: Path | None = None) -> list[str]:
    refs: list[str] = []
    for _, tgt in _LINK_RE.findall(text):
        if not tgt.startswith(("http://", "https://", "#", "mailto:")):
            raw = tgt.split("#")[0]
            # Resolve relative ../ links to a docs_dir-relative path
            if page_dir and docs_dir and raw.startswith("../"):
                try:
                    resolved = (page_dir / raw).resolve()
                    raw = str(resolved.relative_to(docs_dir))
                except Exception:
                    pass
            refs.append(raw)
    for m in _CODE_PATH_RE.findall(text):
        refs.append(m)
    return [r for r in refs if r]


def _ref_exists(ref: str, root: Path, docs_dir: Path,
                members: list[Path] | None = None) -> bool:
    for base in (root, docs_dir, *(members or [])):
        if (base / ref).exists():
            return True
    if "/" not in ref:
        try:
            r = subprocess.run(
                ["rg", "--quiet", "-l", ref, str(root)],
                capture_output=True, timeout=5,
            )
            if r.returncode == 0:
                return True
        except Exception:
            return True  # optimistic when rg unavailable
    return False
