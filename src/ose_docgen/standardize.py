"""Standardize an existing docs/ tree against C4×Diátaxis.

Three file classes (per-file, not per-region — file-level separation):
  GENERATED:  has provenance frontmatter (generated: true). Tool owns these.
  HUMAN:      prose (.md/.mdx) without our marker. Never moved or edited.
              Indexed into standard via generated CROSSWALK.md.
  ASSET:      non-prose / binary / config. Detect & coexist; never touched.

Asset-tree detection: if >50% of all files in docs_dir are ASSET → the dir is
classified NON-DOC (coexist mode: we write to our standard buckets alongside).
"""
from __future__ import annotations

from pathlib import Path

from ose_docgen.provenance import classify, needs_regen, write_generated

_STANDARD_BUCKETS = [
    "01-context", "02-containers", "03-components",
    "04-reference", "05-how-to", "06-decisions", "_meta",
]

_BUCKET_KEYWORDS: list[tuple[str, list[str]]] = [
    ("02-containers", [
        "service", "container", "module", "package", "member",
        "repo", "repository", "api", "server", "client",
    ]),
    ("03-components", ["component", "domain", "community", "layer", "subsystem"]),
    ("04-reference", [
        "reference", "model", "schema", "data", "entity",
        "type", "proto", "grpc", "endpoint",
    ]),
    ("05-how-to", [
        "process", "flow", "guide", "howto", "procedure", "workflow",
        "deploy", "setup", "how-to",
    ]),
    ("06-decisions", ["decision", "adr", "architecture", "design", "rationale", "trade"]),
    ("01-context", [
        "context", "overview", "introduction", "system", "glossary",
        "portal", "map", "onboarding",
    ]),
]


def _bucket_for(path: Path) -> str:
    text = (path.stem + " " + str(path.parent)).lower().replace("_", " ").replace("-", " ")
    for bucket, keywords in _BUCKET_KEYWORDS:
        if any(k in text for k in keywords):
            return bucket
    return "01-context"


def is_asset_dominated(docs_dir: Path) -> bool:
    """True if the majority of files in docs_dir are not prose."""
    n_prose = n_other = 0
    prose_sfx = {".md", ".mdx", ".rst", ".txt"}
    for f in docs_dir.rglob("*"):
        if f.is_file():
            if f.suffix.lower() in prose_sfx:
                n_prose += 1
            else:
                n_other += 1
    return n_other > 0 and n_other > n_prose


def classify_tree(docs_dir: Path) -> dict[str, str]:
    """Classify every file under docs_dir. Returns {rel_path: class}."""
    result: dict[str, str] = {}
    if not docs_dir.exists():
        return result
    for f in sorted(docs_dir.rglob("*")):
        if f.is_file():
            result[str(f.relative_to(docs_dir))] = classify(f)
    return result


def _crosswalk_body(docs_dir: Path, classes: dict[str, str]) -> str:
    _dt = {
        "01-context": "explanation", "02-containers": "explanation/reference",
        "03-components": "explanation", "04-reference": "reference",
        "05-how-to": "how-to", "06-decisions": "explanation",
    }
    rows = []
    for rel, cls in sorted(classes.items()):
        if cls == "human":
            bkt = _bucket_for(docs_dir / rel)
            rows.append(f"| `{rel}` | `{bkt}` | {_dt.get(bkt, 'explanation')} |")
    header = (
        "# Documentation Crosswalk\n\n"
        "Maps existing human-authored docs into C4×Diátaxis standard buckets.\n"
        "Human files are **never moved** — this index is the integration layer.\n\n"
        "| File | Assigned Bucket | Diátaxis Type |\n|---|---|---|\n"
    )
    return header + "\n".join(rows) + ("\n" if rows else "No human-authored files found.\n")


def run(docs_dir: Path, sig: str) -> dict:
    """Classify the docs tree; build CROSSWALK.md; return summary counts.

    Returns: {generated, human, asset, classes, asset_dominated}
    """
    classes = classify_tree(docs_dir)
    n_gen = sum(1 for c in classes.values() if c == "generated")
    n_human = sum(1 for c in classes.values() if c == "human")
    n_asset = sum(1 for c in classes.values() if c == "asset")
    dominated = is_asset_dominated(docs_dir) if docs_dir.exists() else False

    crosswalk_path = docs_dir / "_meta" / "CROSSWALK.md"
    if needs_regen(crosswalk_path, sig):
        write_generated(crosswalk_path, "meta", sig, _crosswalk_body(docs_dir, classes))

    return {
        "generated": n_gen, "human": n_human, "asset": n_asset,
        "classes": classes, "asset_dominated": dominated,
    }
