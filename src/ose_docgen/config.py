"""Configuration: all env vars for ose-docgen (IH-native, LLM-only).

Kill-switch: OSE_DOCGEN=0 → generate() returns empty dict, no output.
No deterministic skeleton — LLM (claude -p) is the only generation path.
"""
from __future__ import annotations

import os

# Kill-switch: 0 = fully off (no output). Default: on.
PIPELINE_ON: bool = os.environ.get("OSE_DOCGEN", "1") != "0"

# Output directory inside each repo (relative to project root).
DOCS_DIR: str = os.environ.get("OSE_DOCGEN_DIR", "docs")

MODEL_HAIKU = "claude-haiku-4-5"
MODEL_SONNET = "claude-sonnet-4-6"

# Ordered list of CLAUDE_CONFIG_DIR paths (two accounts supported).
_raw_profiles = os.environ.get(
    "OSE_DOCGEN_CLAUDE_PROFILES",
    f"{os.path.expanduser('~/.claude')},{os.path.expanduser('~/.claude1')}",
)
CLAUDE_PROFILES: list[str] = [p.strip() for p in _raw_profiles.split(",") if p.strip()]

MAX_PAGES_PER_RUN: int = int(os.environ.get("OSE_DOCGEN_MAX_PAGES", "20"))
TRUTHFULNESS_MIN: float = float(os.environ.get("OSE_DOCGEN_TRUTHFULNESS_MIN", "0.90"))

_PHASE_MODELS: dict[str, str] = {
    "architect": MODEL_SONNET,
    "verify_judge": MODEL_SONNET,
    "explore": MODEL_HAIKU,
    "write": MODEL_HAIKU,
    "skills": MODEL_HAIKU,
}


def model_for_phase(phase: str) -> str:
    """Return model ID for a portal pipeline phase."""
    return _PHASE_MODELS.get(phase, MODEL_HAIKU)
