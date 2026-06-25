"""Shared fixtures for the ose-docgen test suite.

synth_graph_db: minimal sqlite3 graph.db — no OSE import, GPU-free, always runnable.
Schema matches graph_reader.load(): meta, symbols, communities, edges.
"""
from __future__ import annotations

import sqlite3

import pytest


@pytest.fixture
def synth_graph_db(tmp_path):
    """Build a minimal graph.db that satisfies graph_reader.load() and build_skeleton()."""
    db = tmp_path / "graph.db"
    con = sqlite3.connect(str(db))
    con.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE symbols (
            sid TEXT PRIMARY KEY,
            name TEXT,
            qualified_name TEXT,
            kind TEXT,
            file TEXT,
            start_line INTEGER,
            end_line INTEGER,
            language TEXT,
            community_id INTEGER
        );
        CREATE TABLE communities (
            id INTEGER PRIMARY KEY,
            level INTEGER,
            title TEXT,
            summary TEXT,
            member_count INTEGER,
            parent_id INTEGER
        );
        CREATE TABLE edges (
            caller_sid TEXT,
            callee_sid TEXT
        );
    """)
    con.execute("INSERT INTO meta VALUES ('algo_version', '1')")
    files = ["src/main.go", "src/handler.go", "src/db.go"]
    syms = [
        ("s1", "main", "main.main", "function", files[0], 1, 10, "Go", 1),
        ("s2", "New", "handler.New", "function", files[1], 1, 20, "Go", 1),
        ("s3", "Handle", "handler.Handle", "function", files[1], 22, 50, "Go", 1),
        ("s4", "Query", "db.Query", "function", files[2], 1, 30, "Go", 2),
        ("s5", "Connect", "db.Connect", "function", files[2], 32, 45, "Go", 2),
        ("s6", "Init", "db.Init", "function", files[2], 47, 60, "Go", 2),
        ("s7", "Config", "main.Config", "struct", files[0], 12, 25, "Go", 3),
        ("s8", "Run", "main.Run", "function", files[0], 27, 40, "Go", 3),
        ("s9", "Stop", "main.Stop", "function", files[0], 42, 55, "Go", 3),
        ("s10", "Metrics", "handler.Metrics", "function", files[1], 52, 65, "Go", 1),
    ]
    con.executemany(
        "INSERT INTO symbols VALUES (?,?,?,?,?,?,?,?,?)", syms
    )
    comms = [
        (1, 1, "HTTP Handlers", "Handles incoming HTTP requests and routing.", 4, None),
        (2, 1, "Database Layer", "Database access and connection management.", 3, None),
        (3, 1, "Application Core", "Application startup, config, and lifecycle.", 3, None),
        (10, 2, "Service Root", "Top-level service architecture.", 10, None),
    ]
    con.executemany(
        "INSERT INTO communities VALUES (?,?,?,?,?,?)", comms
    )
    edges = [
        ("s1", "s2"), ("s2", "s3"), ("s3", "s4"), ("s4", "s5"),
        ("s1", "s7"), ("s8", "s2"), ("s8", "s4"),
    ]
    con.executemany("INSERT INTO edges VALUES (?,?)", edges)
    con.commit()
    con.close()
    return db
