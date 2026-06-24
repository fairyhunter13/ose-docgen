"""Phase 2: narrate significant pages via Claude Code headless (Haiku 4.5 / Sonnet 4.6).

Subscription-only: subprocess env strips ANTHROPIC_API_KEY; CLAUDE_CONFIG_DIR set per-profile.
Account selector picks the profile with the most 5h+7d headroom; fails over on 429.
Both exhausted → skip narration this cycle (caller falls back to $0 skeleton).
Capped at _MAX_PAGES_PER_RUN per run to prevent runaway cost.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ose_docgen import graph_reader as gr
from ose_docgen.accounts import pick_profile, subprocess_env
from ose_docgen.config import CLAUDE_PROFILES, model_for
from ose_docgen.provenance import needs_regen, write_generated

_TIMEOUT_S = 120
_MAX_PAGES_PER_RUN = 8


def _claude_bin() -> str:
    c = shutil.which("claude")
    if not c:
        raise RuntimeError("'claude' CLI not found in PATH")
    return c


def _run_claude(prompt: str, model: str, docs_dir: Path, config_dir: str) -> str | None:
    """Call claude -p; return text output, '429' on rate-limit, None on failure."""
    cmd = [
        _claude_bin(), "-p", prompt,
        "--model", model, "--output-format", "json",
        "--allowedTools", "Write,Edit",
        "--add-dir", str(docs_dir),
        "--allow-dangerously-skip-permissions",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=_TIMEOUT_S, env=subprocess_env(config_dir))
        if r.returncode != 0:
            err = r.stderr or ""
            return "429" if ("429" in err or "rate_limit" in err.lower()) else None
        data = json.loads(r.stdout)
        if isinstance(data, list):
            for b in data:
                if isinstance(b, dict) and b.get("type") == "text":
                    return b.get("text", "")
        if isinstance(data, dict):
            return data.get("result") or data.get("text") or ""
        return str(data)
    except (subprocess.TimeoutExpired, Exception):
        return None


def _c4_level(page_rel: str) -> str:
    if "01-context" in page_rel:
        return "context"
    if "02-containers" in page_rel:
        return "container"
    if "03-components" in page_rel:
        return "component"
    if "04-reference" in page_rel:
        return "code"
    return "meta"


def _narrate_one(page: Path, page_rel: str, sig: str,
                 ctx_json: str, docs_dir: Path, config_dir: str) -> str:
    """Narrate one page; return 'written'|'skipped'|'429'|'error'."""
    if not needs_regen(page, sig):
        return "skipped"
    prompt = (
        f"Technical doc writer. Narrate `{page_rel}` in `{docs_dir}`. "
        f"Write ONLY the markdown body (no frontmatter). Be concise and factual. "
        f"Fill only placeholder lines starting with `_(`.\n\nContext:\n```json\n{ctx_json}\n```"
    )
    text = _run_claude(prompt, model_for(page_rel), docs_dir, config_dir)
    if text == "429":
        return "429"
    if not text:
        return "error"
    write_generated(page, _c4_level(page_rel), sig, text)
    return "written"


def narrate_significant(gd: gr.GraphData, docs_dir: Path, sig: str) -> dict[str, str]:
    """Narrate significant pages with subscription account load-balancing."""
    saturated: set[str] = set()
    results: dict[str, str] = {}
    written = 0
    candidates = [p for p in sorted(docs_dir.rglob("*.md")) if needs_regen(p, sig)]
    if not candidates:
        return results
    ctx_json = json.dumps({
        "project": gd.project_path.name,
        "n_symbols": len(gd.symbols),
        "n_l1": len(gd.l1_communities),
        "n_l2": len(gd.l2_communities),
        "l2_titles": [c.title for c in gd.l2_communities if c.title][:20],
        "l1_titles": [c.title for c in gd.l1_communities if c.title][:30],
    }, ensure_ascii=False)[:4000]
    for page in candidates:
        if written >= _MAX_PAGES_PER_RUN:
            break
        page_rel = str(page.relative_to(docs_dir))
        profile = pick_profile(CLAUDE_PROFILES, saturated=saturated)
        if not profile:
            results[page_rel] = "no_profile"
            continue
        status = _narrate_one(page, page_rel, sig, ctx_json, docs_dir, profile)
        results[page_rel] = status
        if status == "429":
            saturated.add(profile)
        elif status == "written":
            written += 1
    return results
