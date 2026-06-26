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

    Checks file existence with a basename fallback: if the exact relative path
    doesn't match, try any file with the same basename anywhere under the root.
    This catches fabricated filenames while tolerating LLM path-prefix mistakes
    (e.g. 'promo.go' when the real path is 'promo/promo.go').
    """
    errors = []
    for m in _CITE_RE.finditer(text):
        fpath, lineno = m.group(1).strip(), int(m.group(2))
        target = (project_root / fpath).resolve()
        if target.is_file():
            continue
        basename = Path(fpath).name
        if not any(True for _ in project_root.rglob(basename)):
            errors.append(f"{fpath}:{lineno} -- file not found")
    return errors
