# cedar_odcs

The mechanism, with no use case named in it: an engine and two
interfaces. Extracted from iterations 6 through 10 as the reservations
use case demanded, with the orders use case holding parity on every
move.

- `engine/usecase.py`: the descriptor a use case hands the engine:
  resource entity type, which payload fields are attributes and of
  what type, the id field, the verbs of each round, the tool table.
- `engine/identities.py`: the projection from token claims to the
  Cedar parties (RFC 8693 `sub` and `act`), roles as the union of
  token and store.  The descriptor's `ClaimsMapping` names the
  subject, roles, and actor claims; a Cognito access token uses
  `username` and `cognito:groups`.
- `engine/enforce.py`: the request leg (verb round, payload round) and
  the response leg (row round, field round), leaf by leaf, by path,
  with one decision per distinct path per call. Resource entities come
  from the payload.
- `engine/contract.py`: the two build stages. `pull`, Unity Catalog to
  the ODCS contract, for a use case that has a catalog; `build`, the
  committed contract to path-keyed tag maps and the resource entity
  declaration. Nested columns from the catalog's `type_json`, nested
  levels from path-scoped tag keys.
- `engine/grants.py`: the field-level read and write policies keyed on
  classification, rendered from `contract/grants.yaml` into
  `contract/generated/grants.cedar` by `build`.  The use case writes
  the verb policies; `UseCase.policies`, the corpus, `validate`, and
  `prove` read `policies.cedar` with the rendered grants appended.
- `engine/corpus.py`: the engine-independent corpus runner.
- `cli/main.py`: the `cedar-odcs` command (iteration 14): run-tests,
  authorize, dry-run, check-access, share, pull, build, tools, validate,
  prove, check.  `tools` is the tool schema gate: with `tools.json`
  beside `usecase.py`, each object or list tool's `outputSchema` must
  name exactly the contract's leaves, and `check` runs it after build.
- `gateway/handlers.py`: the AgentCore Gateway handlers for MCP
  targets, with presented facts copied from tool arguments into
  context; also strict bearer decoding, a Gateway concern.  With
  `CEDAR_ODCS_RECORD` set, each handler logs its inbound event as one
  JSON line, for saving live calls as fixtures.
- `gateway/handler.py`: the two AWS Lambda entry points, loading a use
  case by the `CEDAR_ODCS_USE_CASE` environment variable.

A use case directory (`usecases/<name>/`) holds `usecase.py`,
`policies.cedar`, `facts.json`, `principals.cedarschema`,
`actions.cedarschema`, the ODCS contract, `unity/` fixtures when a
catalog is its source, the build's committed
outputs, `tests/` corpora, `events/` Gateway fixtures, and its tests.
`uv run python usecases/<name>/build.py` rebuilds the artifacts.

`history/what-reservations-changed.html` is the writeup of what the mechanism
had to change to admit the reservation use case, taken from the diffs
of iterations 11 through 13.
