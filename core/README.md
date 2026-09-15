# core

The mechanism, with no use case named in it. Extracted from iterations
6 through 10 as the reservations use case demanded, with the orders
use case holding parity on every move.

- `usecase.py`: the descriptor a use case hands core: resource entity
  type, which payload fields are attributes and of what type, the id
  field, the verbs of each round, the tool table.
- `claims.py`: the projection from token claims to the Cedar parties
  (RFC 8693 `sub` and `act`), roles as the union of token and store,
  and strict bearer decoding.
- `enforce.py`: the request leg (verb round, payload round) and the
  response leg (row round, field round), leaf by leaf, by path, with
  one decision per distinct path per call. Resource entities come from
  the payload.
- `interceptor.py`: the AgentCore Gateway handlers for MCP targets,
  with presented facts copied from tool arguments into context.
- `contract.py`: the build, Unity Catalog to ODCS to path-keyed tag
  maps and the resource entity declaration; nested columns from the
  catalog's `type_json`, nested levels from path-scoped tag keys.
- `corpus.py`: the engine-independent corpus runner.
- `cli.py`: the `cedar-osdc` command (iteration 14): run-tests, authorize,
  dry-run, check-access, share, build, validate, prove.

A use case directory (`usecases/<name>/`) holds `usecase.py`,
`policies.cedar`, `facts.json`, `principals.cedarschema`,
`actions.cedarschema`, `unity/` fixtures, the build's committed
outputs, `tests/` corpora, `events/` Gateway fixtures, and its tests.
`uv run python usecases/<name>/build.py` rebuilds the artifacts.

`what-reservations-changed.html` is the writeup of what core had to
change to admit the reservation use case, taken from the diffs of
iterations 11 through 13.
