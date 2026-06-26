"""Subscription account selector — picks the Claude profile with most headroom.

Supports two accounts (e.g. ~/.claude + ~/.claude-account1) via CLAUDE_CONFIG_DIR isolation.
Reads 5h+7d utilization from the undocumented oauth/usage endpoint using the OAuth token
from each profile's .credentials.json, with a 5-minute local cache per profile.

Selection logic:
  1. Enumerate OSE_DOCGEN_CLAUDE_PROFILES (ordered).
  2. For each: check .credentials.json exists + read cached/live 5h+7d utilization.
  3. Pick the active profile (creds valid, not at 100%) with the LOWEST utilization.
  4. On a 429 from the chosen profile, mark it temporarily saturated and try the next.
  5. Both exhausted → return None (caller falls back to $0 skeleton).

Note: ANTHROPIC_API_KEY must be absent from the subprocess env so the subscription
      credentials in CLAUDE_CONFIG_DIR are used, not API billing.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_CACHE_TTL_S = 300  # 5-minute refresh per profile
_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
_BETA_HEADER = "oauth-2025-04-20"


@dataclass
class ProfileUsage:
    config_dir: str
    five_hour_pct: float   # 0.0 – 1.0
    seven_day_pct: float   # 0.0 – 1.0
    valid: bool            # False if creds missing or fetch failed


def _load_token(config_dir: str) -> str | None:
    creds = Path(config_dir) / ".credentials.json"
    if not creds.exists():
        return None
    try:
        data = json.loads(creds.read_text(encoding="utf-8"))
        # Flat token keys (older format)
        flat = data.get("oauth_token") or data.get("access_token") or data.get("token")
        if flat:
            return flat
        # Nested claudeAiOauth structure (Claude Code >= 2.x)
        nested = data.get("claudeAiOauth") or {}
        return nested.get("accessToken") or nested.get("access_token")
    except Exception:
        return None


def _cache_path(config_dir: str) -> Path:
    return Path(config_dir) / "usage-exact.json"


def _read_cache(config_dir: str) -> dict | None:
    p = _cache_path(config_dir)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if time.time() - data.get("_ts", 0) < _CACHE_TTL_S:
            return data
    except Exception:
        pass
    return None


def _write_cache(config_dir: str, data: dict) -> None:
    data["_ts"] = time.time()
    try:
        _cache_path(config_dir).write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def _fetch_usage(token: str) -> dict | None:
    req = urllib.request.Request(
        _USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": _BETA_HEADER,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def get_profile_usage(config_dir: str) -> ProfileUsage:
    """Return usage metrics for one profile (cached up to 5 min)."""
    token = _load_token(config_dir)
    if not token:
        return ProfileUsage(
            config_dir=config_dir, five_hour_pct=1.0, seven_day_pct=1.0, valid=False
        )

    cached = _read_cache(config_dir)
    if cached:
        return ProfileUsage(
            config_dir=config_dir,
            five_hour_pct=cached.get("five_hour_pct", 0.0),
            seven_day_pct=cached.get("seven_day_pct", 0.0),
            valid=True,
        )

    data = _fetch_usage(token)
    if not data:
        # Assume available if we can't read (be optimistic; 429 will trigger failover)
        return ProfileUsage(config_dir=config_dir, five_hour_pct=0.0, seven_day_pct=0.0, valid=True)

    # Nested format (current): {"five_hour": {"utilization": 25.0}, ...} — percentages 0-100
    # Flat format (old/unknown): {"five_hour_utilization": 0.25} — fractions 0-1
    if "five_hour" in data:
        five_h = float((data["five_hour"] or {}).get("utilization", 0)) / 100.0
        seven_d = float((data["seven_day"] or {}).get("utilization", 0)) / 100.0
    else:
        five_h = float(data.get("five_hour_utilization", 0.0))
        seven_d = float(data.get("seven_day_utilization", 0.0))
    _write_cache(config_dir, {"five_hour_pct": five_h, "seven_day_pct": seven_d})
    return ProfileUsage(
        config_dir=config_dir, five_hour_pct=five_h, seven_day_pct=seven_d, valid=True
    )


def pick_profile(profiles: list[str], *, saturated: set[str] | None = None) -> str | None:
    """Pick the active profile with the most headroom. Returns None if all exhausted."""
    saturated = saturated or set()
    candidates: list[ProfileUsage] = []
    for p in profiles:
        if p in saturated:
            continue
        usage = get_profile_usage(p)
        if not usage.valid:
            continue
        if usage.five_hour_pct >= 1.0 or usage.seven_day_pct >= 1.0:
            continue  # at limit
        candidates.append(usage)

    if not candidates:
        return None
    # Pick least-used (lower of max(5h, 7d) across candidates)
    best = min(candidates, key=lambda u: max(u.five_hour_pct, u.seven_day_pct))
    return best.config_dir


def subprocess_env(config_dir: str) -> dict[str, str]:
    """Build a clean subprocess environment for Claude Code.

    - Sets CLAUDE_CONFIG_DIR to the chosen profile.
    - REMOVES ANTHROPIC_API_KEY so subscription credentials are used, not API billing.
    - Sets CLAUDE_CODE_SAFE_MODE=1 to prevent IPC deadlock when called from within
      an active Claude Code session (parent-IPC hang otherwise).
    - Inherits PATH so the 'claude' binary is found.
    """
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    env["CLAUDE_CONFIG_DIR"] = config_dir
    env["CLAUDE_CODE_SAFE_MODE"] = "1"
    return env
