"""Pytest configuration for the Friday repository.

The repository root is discovered from this file instead of relying on a
machine-specific absolute path. This keeps local Windows development and CI
portable across checkout locations.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
root_string = str(ROOT)
if root_string not in sys.path:
    sys.path.insert(0, root_string)
