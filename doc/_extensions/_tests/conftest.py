import sys
from pathlib import Path

# Make _extensions/ importable without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIXTURES = Path(__file__).parent / "fixtures"
