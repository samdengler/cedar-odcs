"""uv run python usecases/hr/build.py: rebuild the committed artifacts,
the Cedar files from the hand-written contract. There is no catalog,
so there is no pull."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from cedar_odcs.engine.contract import build, write  # noqa: E402
from usecases.hr.usecase import CONTRACT, ROOT  # noqa: E402

if __name__ == "__main__":
    outputs = build(ROOT, CONTRACT)
    write(ROOT, outputs)
    for rel in outputs:
        print("wrote", rel)
