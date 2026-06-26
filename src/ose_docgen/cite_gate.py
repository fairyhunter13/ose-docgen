"""Citation-resolution gate: verify every [code: file:line] in generated markdown.

Deterministic post-generation guard — no LLM. Catches hallucinated citations
before they enter any KB or index. Called by portal._write_pages().
"""
from __future__ import annotations

import re
from pathlib import Path

_CITE_RE = re.compile(r'\[code:\s*([^:\]]+):(\d+)\]')


def check_citations(text: str, project_root: Path) -> list[str]:
    """Return list of unresolvable [code: file:line] citations; empty if all resolve.

    Only checks that cited files exist — line-number precision is secondary (the LLM
    often generates slightly out-of-range numbers for small files, which is a quality
    issue rather than a hallucination). File-not-found is the blocking error.
    """
    errors = []
    for m in _CITE_RE.finditer(text):
        fpath, lineno = m.group(1).strip(), int(m.group(2))
        target = (project_root / fpath).resolve()
        if not target.is_file():
            errors.append(f"{fpath}:{lineno} -- file not found")
    return errors
