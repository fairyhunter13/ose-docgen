"""ose-docgen — in-repo C4×Diátaxis information hierarchy generator.

Data-contract entry point: generate() takes graph artifacts from opencode-search-engine
and writes a real docs/ tree into the target repository. No opencode_search import.
"""
from ose_docgen.generate import generate

__all__ = ["generate"]
__version__ = "0.1.0"
