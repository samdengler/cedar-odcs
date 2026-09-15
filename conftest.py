# The root test run imports every use case's tests by path
# (--import-mode=importlib). core/ is a package at the repository root;
# put the root on sys.path so `import core` resolves everywhere.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
