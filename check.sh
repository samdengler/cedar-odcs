#!/bin/sh
# Every check the repository has, in one command: each iteration's
# test corpus and wrappers, then the symbolic proofs. Exits nonzero
# if either fails. Run from anywhere.
set -e
cd "$(dirname "$0")"
uv run pytest -q
cd analysis && cargo run --quiet
