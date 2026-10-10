import sys
from pathlib import Path

# The module under test sits at the repository root; tests live in tests/.
sys.path.insert(0, str(Path(__file__).parent))
