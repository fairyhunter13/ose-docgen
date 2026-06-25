"""Machine-enforced no-skip policy for the ose-docgen test suite.

Mirrors test_no_code_semantic_regex.py::test_no_skip_markers_in_live_suite in the OSE suite.
Scans tests/*.py for forbidden skip/xfail markers and fails if any are found.
"""
from __future__ import annotations

from pathlib import Path

_FORBIDDEN = ("pytest.skip(", "pytest.xfail(", "@pytest.mark.xfail", "@pytest.mark.skipif")
_TESTS_DIR = Path(__file__).parent


def test_no_skip_markers_in_docgen_suite() -> None:
    """Every test in tests/*.py must run unconditionally — no skips, no xfail."""
    violations: list[str] = []
    for py_file in sorted(_TESTS_DIR.glob("*.py")):
        if py_file.name == Path(__file__).name:
            continue  # skip self
        text = py_file.read_text(encoding="utf-8")
        for marker in _FORBIDDEN:
            if marker in text:
                violations.append(f"{py_file.name}: contains {marker!r}")
    assert not violations, (
        "No-skip policy violated — remove these markers and make the tests unconditional:\n"
        + "\n".join(violations)
    )
