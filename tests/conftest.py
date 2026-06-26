"""Shared fixtures for the ose-docgen test suite.

synth_repo: minimal source tree — no OSE import, GPU-free, always runnable.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def synth_repo(tmp_path):
    """Build a minimal source tree that satisfies build_skeleton() and repo_parser."""
    root = tmp_path / "project"
    src = root / "src"
    src.mkdir(parents=True)
    (src / "main.go").write_text('package main\nfunc main() {}\n')
    (src / "handler.go").write_text('package main\nfunc Handle() {}\n')
    (src / "db.go").write_text('package db\nfunc Query() {}\n')
    lib = root / "lib"
    lib.mkdir()
    (lib / "util.go").write_text('package lib\nfunc Helper() {}\n')
    (lib / "config.go").write_text('package lib\ntype Config struct{}\n')
    return root
