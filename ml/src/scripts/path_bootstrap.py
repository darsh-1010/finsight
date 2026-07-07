"""Ensure project imports work when running scripts directly.

When executing a script via a file path (e.g. `python src/scripts/foo.py`), the
working directory may not be the project root, so `import src...` can fail.

Import this module first to add the project root to `sys.path`.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT_STR = str(PROJECT_ROOT)

if PROJECT_ROOT_STR not in sys.path:
    sys.path.append(PROJECT_ROOT_STR)
