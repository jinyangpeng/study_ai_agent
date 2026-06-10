"""pytest configuration.

* Ensures the project root is on ``sys.path`` so ``from src.core import ...``
  works under ``pytest`` without an editable install.
* Place shared fixtures here as the suite grows.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
