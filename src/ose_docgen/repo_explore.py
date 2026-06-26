"""OSE-free repo discovery + Haiku explore-pass for the portal.

discover_members(root): scan root for symlinks outside root (no OSE import)
portal_sig(root): mtime fingerprint for idempotency
run_claude_portal(...): shared claude -p subprocess helper
explore_repo(root, profile): Haiku explore-pass → JSON brief (cached)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from ose_docgen.accounts import subprocess_env

_IGNORED = frozenset({
    ".git", "__pycache__", "node_modules", "vendor", ".venv", "venv",
    ".tox", "dist", "build", ".cache",
})
_BRIEF_CACHE: dict[str, dict] = {}  # keyed by path:sig


def _looks_like_repo(p: Path) -> bool:
    return (p / ".git").exists() or any(
        p.glob(g) for g in ("*.go", "*.java", "*.py", "go.mod", "pom.xml", "package.json")
    )


def discover_members(root: Path) -> list[Path]:
    """Scan root for symlinked sub-repos resolving outside root (OSE-free)."""
    root = root.resolve()
    out: list[Path] = []
    try:
        for dirpath, dirs, _ in os.walk(str(root), followlinks=False):
            dirs[:] = [d for d in dirs if d not in _IGNORED]
            for d in list(dirs):
                p = Path(dirpath) / d
                if not p.is_symlink():
                    continue
                t = p.resolve()
                if t != root and not t.is_relative_to(root) and _looks_like_repo(t):
                    out.append(t)
                    dirs.remove(d)
    except OSError:
        pass
    return out


def portal_sig(root: Path) -> str:
    """mtime fingerprint of repo top-level entries for idempotency."""
    total = 0
    try:
        total = sum(int(f.stat().st_mtime_ns) for f in root.iterdir() if not f.name.startswith("."))
    except OSError:
        pass
    return hashlib.sha1(f"{root}:{total}".encode()).hexdigest()[:16]


def _claude() -> str:
    c = shutil.which("claude")
    if not c:
        raise RuntimeError("'claude' CLI not found in PATH")
    return c


def run_claude_portal(
    prompt: str, model: str, *,
    add_dirs: list[str], tools: str = "Read,Bash",
    profile: str, timeout: int = 120, cwd: str | None = None,
) -> str | None:
    """Run claude -p headless; return extracted text or None on failure."""
    cmd = [_claude(), "-p", prompt, "--model", model,
           "--output-format", "json", "--allow-dangerously-skip-permissions"]
    if tools is not None:
        cmd += ["--allowedTools", tools]
    for d in add_dirs:
        cmd += ["--add-dir", d]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, env=subprocess_env(profile), cwd=cwd)
        if r.returncode != 0:
            return None
        data = json.loads(r.stdout)
        if isinstance(data, list):
            for b in data:
                if isinstance(b, dict) and b.get("type") == "text":
                    return b.get("text", "")
        if isinstance(data, dict):
            return data.get("result") or data.get("text") or ""
        return str(data) or None
    except Exception:
        return None


def _from_json(text: str | None) -> dict | None:
    """Extract and parse JSON from Claude text (handles ```json blocks)."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 1)[1].lstrip("json").rsplit("```", 1)[0].strip()
    try:
        return json.loads(t)
    except Exception:
        return None


def explore_repo(root: Path, *, profile: str, timeout: int = 120) -> dict:
    """Haiku explore-pass on one repo → JSON brief. Cached by portal_sig."""
    from ose_docgen.config import model_for_phase
    key = f"{root}:{portal_sig(root)}"
    if key in _BRIEF_CACHE:
        return _BRIEF_CACHE[key]
    prompt = (
        "Analyze this repository. Output ONLY valid JSON (no markdown wrapper) with keys: "
        "primary_language (str), frameworks (list[str]), services (list[str]), "
        "datastores (list[str]), migrations (list[str] relative paths, empty if none), "
        "ci_files (list[str] relative CI/CD config paths), integrations (list[str]), "
        "existing_docs (list[str] relative paths of human-written docs), "
        "summary (1-2 sentences). Be factual — only what you can verify in the files."
    )
    text = run_claude_portal(prompt, model_for_phase("explore"),
                              add_dirs=[str(root)], tools="Read,Bash",
                              profile=profile, timeout=timeout, cwd=str(root))
    brief = _from_json(text) or {"summary": "explore failed", "_error": True}
    brief.update({"_root": str(root), "_rel": root.name, "_sig": portal_sig(root)})
    _BRIEF_CACHE[key] = brief
    return brief
