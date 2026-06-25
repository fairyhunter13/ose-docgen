"""Configuration: all env vars for ose-docgen.

All flags have safe defaults so the tool works out-of-the-box with $0 deterministic output.
The LLM layers are opt-in via OSE_DOCGEN_LLM=1.
"""
from __future__ import annotations

import os

# Master kill-switch: 0 = fully deterministic skeleton, $0, no Claude calls.
# Default: off (safe for CI / first run).
LLM_ON: bool = os.environ.get("OSE_DOCGEN_LLM", "0") != "0"

# Directory inside each repo where docs are written (relative to project root).
DOCS_DIR: str = os.environ.get("OSE_DOCGEN_DIR", "docs")

# Whether the auto-pipeline wires docgen into _enrich_project.
PIPELINE_ON: bool = os.environ.get("OSE_DOCGEN", "1") != "0"

# Model tier.
# "haiku"  → claude-haiku-4-5  (default, summaries/explanation, ~90% quality, ⅓ cost)
# "sonnet" → claude-sonnet-4-6 (opt-in for genuinely synthetic pages: ADR, data-model, context)
TIER: str = os.environ.get("OSE_DOCGEN_TIER", "haiku").lower()

MODEL_HAIKU = "claude-haiku-4-5"
MODEL_SONNET = "claude-sonnet-4-6"

# Synthetic pages that warrant Sonnet-tier reasoning when OSE_DOCGEN_TIER=sonnet.
SYNTHETIC_PAGES = {"01-context/system-context.md", "data-model.md", "06-decisions"}

def model_for(page_rel: str) -> str:
    """Return the appropriate model ID for this page path (relative to docs/)."""
    if TIER == "sonnet":
        # Escalate only genuinely synthetic pages; bulk stays on Haiku.
        for synthetic in SYNTHETIC_PAGES:
            if page_rel.startswith(synthetic):
                return MODEL_SONNET
    return MODEL_HAIKU

# Ordered list of CLAUDE_CONFIG_DIR paths (two accounts supported).
# Usage: pick the active account with the most headroom; fail over on 429.
_raw_profiles = os.environ.get(
    "OSE_DOCGEN_CLAUDE_PROFILES",
    f"{os.path.expanduser('~/.claude')},{os.path.expanduser('~/.claude1')}",
)
CLAUDE_PROFILES: list[str] = [p.strip() for p in _raw_profiles.split(",") if p.strip()]

# Schema version this tool understands (must match ALGO_VERSION+HIER_VERSION in OSE).
# Bump when graph.db schema changes so we can detect incompatible data contracts.
GRAPH_CONTRACT_VERSION = "fg1+lp2"

# Portal (A): agentic repo-native hierarchy generator.
PORTAL_ON: bool = os.environ.get("OSE_DOCGEN_PORTAL", "0") != "0"
TRUTHFULNESS_MIN: float = float(os.environ.get("OSE_DOCGEN_TRUTHFULNESS_MIN", "0.90"))
MAX_PAGES_PER_RUN: int = int(os.environ.get("OSE_DOCGEN_MAX_PAGES", "20"))

_PHASE_MODELS: dict[str, str] = {
    "architect": MODEL_SONNET,
    "verify_judge": MODEL_SONNET,
    "explore": MODEL_HAIKU,
    "write": MODEL_HAIKU,
    "skills": MODEL_HAIKU,
}


def model_for_phase(phase: str) -> str:
    """Return model ID for a portal pipeline phase (explore/architect/write/skills/verify_judge)."""
    return _PHASE_MODELS.get(phase, MODEL_HAIKU)
