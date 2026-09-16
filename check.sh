#!/bin/sh
# Every check the repository has, in one command: the engine's and the
# use cases' tests, then the proofs of each use case, then the proofs
# of the history chain. Exits nonzero if any fails. Run from anywhere.
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"
uv run pytest -q
cd analysis
for usecase in hello orders reservations; do
  cargo run --quiet -- prove "$ROOT/usecases/$usecase"
done
cargo run --quiet -- prove-history "$ROOT"
