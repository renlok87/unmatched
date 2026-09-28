import sys
from pathlib import Path

QA010_DIR = Path(__file__).resolve().parents[1]
if str(QA010_DIR) not in sys.path:
    sys.path.insert(0, str(QA010_DIR))
