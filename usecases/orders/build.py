"""uv run python usecases/orders/build.py: rebuild the committed artifacts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from cedar_odcs.engine.contract import build, write  # noqa: E402
from usecases.orders.usecase import BUILD, ROOT  # noqa: E402

if __name__ == "__main__":
    outputs = build(ROOT, **BUILD)
    write(ROOT, outputs)
    for rel in outputs:
        print("wrote", rel)
