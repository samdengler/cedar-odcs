#!/bin/sh
# Every check the repository has, in one command: the engine's and the
# use cases' tests, then check on each use case (build, validate,
# run-tests, prove), then the proofs of the history chain. Exits
# nonzero if any fails. Run from anywhere.
set -e
cd "$(dirname "$0")"
uv run pytest -q
uv run cedar-osdc check usecases/hello
uv run cedar-osdc check usecases/orders
uv run cedar-osdc check usecases/reservations
uv run cedar-osdc prove
