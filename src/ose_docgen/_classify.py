"""Tier-1 semantic bucket classifier: Haiku-4.5 classifies human docs by content.

One batched, prompt-cached, constrained-output call per repo.
Result cached in provenance.json by content hash → one-time cost per doc (idempotent).
Falls back to {} on any error; caller uses Tier-0 keyword mapping as the floor.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from ose_docgen.provenance import load_provenance, save_provenance

_BUCKETS = [
    "01-context", "02-containers", "03-components",
    "04-reference", "05-how-to", "06-decisions",
]
_TAXONOMY = " | ".join(_BUCKETS)
_TIMEOUT_S = 60
_SNIPPET_LINES = 50
_SNIPPET_CHARS = 600


def classify_buckets_semantic(
    docs_dir: Path, human_rels: list[str], meta_dir: Path
) -> dict[str, str]:
    """Return {rel_path: bucket} for human docs using Haiku-4.5.

    Falls back to {} on quota exhaustion, missing claude binary, or any error.
    """
    if not human_rels:
        return {}

    # Content hash for cache invalidation
    h = hashlib.sha1()
    snippets: dict[str, str] = {}
    for rel in human_rels:
        try:
            lines = (docs_dir / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            snippets[rel] = "\n".join(lines[:_SNIPPET_LINES])
        except OSError:
            snippets[rel] = ""
        h.update(snippets[rel].encode())
    content_hash = h.hexdigest()[:16]

    prov = load_provenance(meta_dir)
    cached = prov.get("crosswalk_cache", {})
    if cached.get("hash") == content_hash and "buckets" in cached:
        return dict(cached["buckets"])

    try:
        from ose_docgen.accounts import pick_profile, subprocess_env  # noqa: PLC0415
        from ose_docgen.config import CLAUDE_PROFILES, MODEL_HAIKU  # noqa: PLC0415

        profile = pick_profile(CLAUDE_PROFILES)
        if not profile:
            return {}
        claude = shutil.which("claude")
        if not claude:
            return {}

        entries = "\n\n".join(
            f'FILE: {rel}\n"""\n{s[:_SNIPPET_CHARS]}\n"""' for rel, s in snippets.items()
        )
        prompt = (
            f"Classify each FILE into exactly one C4xDiataxis bucket: {_TAXONOMY}\n"
            "Return ONLY a JSON object {\"<filename>\": \"<bucket>\"}. No other text.\n\n"
            + entries
        )
        r = subprocess.run(
            [claude, "-p", prompt, "--model", MODEL_HAIKU,
             "--output-format", "text", "--allowedTools", ""],
            capture_output=True, text=True,
            timeout=_TIMEOUT_S, env=subprocess_env(profile),
        )
        if r.returncode != 0:
            return {}
        raw = r.stdout.strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start < 0 or end <= start:
            return {}
        parsed: dict = json.loads(raw[start:end])
        valid = {k: v for k, v in parsed.items() if v in _BUCKETS and k in human_rels}
        prov["crosswalk_cache"] = {"hash": content_hash, "buckets": valid}
        save_provenance(meta_dir, prov)
        return valid
    except Exception:
        return {}
