# Iteration directories are standalone uv projects, not Python
# packages. The root test run imports test files by path
# (--import-mode=importlib), which does not put this directory on
# sys.path; add it so `import write_gate` resolves.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
