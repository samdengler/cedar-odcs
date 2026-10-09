"""uv run python usecases/orders/build.py: rebuild the committed artifacts,
the contract from the catalog fixtures and the Cedar files from the contract."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from cedar_odcs.engine.contract import build, pull, write  # noqa: E402
from usecases.orders.usecase import CONTRACT, PULL, ROOT  # noqa: E402

if __name__ == "__main__":
    outputs = pull(ROOT, CONTRACT, **PULL)
    write(ROOT, outputs)
    outputs.update(build(ROOT, CONTRACT))
    write(ROOT, outputs)
    for rel in outputs:
        print("wrote", rel)
