# Reorganization plan

A plan for review, then tasks, then overnight runs. It covers the
repository layout, the shape of a use case, the split of the tool
into an engine and two interfaces, proofs per use case, and the test
case format. Nothing here changes what the policies decide; every
check that is green before a run is green after it. Revised after a
critical review on 2026-09-15; the review's findings are folded in and
its numbering is referenced where a choice was made.

## The sentence

A use case is a folder with four things, a data contract, policies,
tests, and guardrails; one command checks the folder; the same folder
is what the Gateway loads.

## Target layout

```
README.md         what it is, run hello in three commands, then the map below
index.html        one landing page pointing at the README, the path, and the history
cedar_odcs/       the tool: engine, command line, Gateway handlers (Python)
analysis/         the symbolic analysis runner (Rust) and the bundled solver
usecases/         one folder per domain, hello among them
learn/            the path and the guide
designs/          plans for work not yet done, this document among them
history/          how it was built: the nine snapshots and every design narrative
check.sh  conftest.py  pyproject.toml  uv.lock
```

Six directories and five files at the top level, against fourteen
directories and six files today. The analysis crate stays where it
is and keeps its name: a Rust crate inside the Python package would
put its build directory and the solver into the wheel, which the
review verified at 1.9 GB (finding 4), and "analysis" is Cedar's own
word for what it does; the crate poses questions to the symbolic
compiler and cvc5, which are what proves them. The root `conftest.py`
stays; it is what puts the repository root on the import path for the
tests.

## The shape of a use case

```
usecases/reservations/
  usecase.py                 the descriptor: entity type, attributes, verbs, tool table, fetch
  policies.cedar
  guardrails/                invariants: forbids that must change nothing
  contract/
    unity/                   the table and its column tags, as Unity Catalog returns them
    reservation.odcs.yaml    generated
    generated/               the tag maps and the Cedar schema, generated
  principals.cedarschema     hand-written build input: who can be a principal
  actions.cedarschema        hand-written build input: the verbs and their context
  facts.json                 sample users, roles, and records the tests refer to
  entities.json              facts plus the generated maps, built, committed
  tests/
    test-cases/              request in, decision expected; every JSON file here runs
    identities/              who can call: the claims of each, one file per identity
    responses/               what the API returns, saved, one file per record
    events/                  Gateway interceptor events, request and response, for the handler tests
    test_*.py                the use case's own tests
  build.py                   rebuilds contract/ and entities.json
```

The same shape for hello, orders, reservations, and a new domain;
hello moves from `learn/` to `usecases/hello` so there is one shape
and one loop (finding 17), and step 1 of the learning path points at
it. Identities, responses, and events are fixtures: data the engine
or a handler reads as it would read the real thing. The one mock in a
use case is the descriptor's fetch, which for a write that needs the
record first reads `tests/responses/<id>.json` instead of calling the
API, and is replaced by a real read at deployment. Today's
`records.json` and `records/` fold into `tests/responses/`.

## One command

```sh
cedar-odcs check usecases/reservations
```

Runs, in order, stopping at the first failure:

1. `build`: catalog to contract to maps and schema; fails on an unclassified column.
2. `validate`: the policies against the built schema, through the official `cedar` command when it is on the path, otherwise through `cedarpy.validate_policies`, which the installed binding already provides (finding 12). A missing `cedar` is not a failure.
3. `run-tests`: every file under `tests/test-cases/`.
4. `prove`: every file under `guardrails/`, plus never-errors for every policy. Needs cargo and cvc5; when they are missing, `check` says so and stops, since a use case is not checked without its proofs.

The four stay callable one at a time. `dry-run`, `check-access`, and
`share` stay for asking questions. `new` stays deferred; the guide
says to copy hello.

## The tool: one package, an engine and two interfaces

```
cedar_odcs/
  engine/
    contract.py      the build: Unity Catalog to ODCS to maps and schema
    identities.py    the projection from claims to the Cedar parties (today claims.py)
    calls.py         a tool call to a decision, defined below
    enforce.py       the two legs by path, the pre-fetch, entities from payloads
    usecase.py       the descriptor
    corpus.py        the test case runner
  cli/
    main.py          arguments in, words out
  gateway/
    handlers.py      interceptor events in, Gateway results out; bearer decoding
    handler.py       the two Lambda entry points, loading a use case by name
analysis/
  Cargo.toml, src/   as today; the runner takes the directory to prove as an argument
```

The line: the engine owns everything that decides, including the
meaning of a tool call. The interfaces own translation only.

`calls.py` is the extraction of the three private methods the handler
has today, `_resource`, `_context`, and `_payload`, plus the row id
(finding 14):

```python
@dataclass
class Call:
    action: str      # 'Action::"UpdateReservation"'
    resource: str    # 'Reservation::"ABC123"' or 'Collection::"orders"'
    payload: dict | None
    context: dict    # the presented facts, upper-cased, or empty
    row_id: str | None

def call(use_case, tool_name: str, arguments: dict) -> Call
    # raises ValueError for an unknown tool, an unusable id, an
    # unexpected argument, or a partial set of presented facts
```

The engine's `check_call` and `filter_object` / `filter_rows` take a
`Call`. The handlers build a `Call` from an event and the command line
builds one from arguments; neither reaches into the other. The
agreement test (finding 13): for every request event and its
matching response event that name a governed tool, the handler's
translation and the command line's translation of the same call
produce the same `Call`, the same `CallDecision`, and the same
`RowsDecision`. Engine values are compared, never printed words or
Gateway envelopes.

## Proofs per use case

Everything that states what must be true of a use case lives in the
use case; only the runner is shared.

- `guardrails/*.cedar`: every file applies to the folder's current
  policies. No manifest. Retiring a guardrail is deleting the file,
  which git records.
- `prove DIR` proves each guardrail is a no-op against the policies,
  and that no policy can error under the built schema.
- Non-vacuity is a separate task after the move (finding 6), because
  it is the one proof the project has never run and could fail on a
  file that is correct today. Stated precisely: for each guardrail
  and each request environment of the built schema, `permit(principal,
  action, resource);` alone and `permit(principal, action, resource);`
  plus the guardrail must differ in at least one environment. That is
  "some request satisfies the guardrail's scope and condition", it
  reuses the runner's difference check unchanged, and a misspelled
  level fails it. It lands as reporting only; turning it into a
  failure is a decision after the first run.

## The history chain

The chain of iterations 1 through 10, with its pairs, declared
revisions, restrictions, specs, hand-written schemas, and retired
guardrails, is a fact about history. It is proven by `prove-history`,
which `check.sh` calls, and a newcomer never meets it.

What `prove-history` reads (finding 2): the tables `ITERATIONS`,
`PAIRS`, `RETIRED`, and `SCHEMA_OVERRIDES`, compiled into the runner
with paths rewritten; policies from `history/<name>/policies.cedar`
and from the live orders use case, which is the chain's final member;
schemas from `history/chain/schemas/` for iterations 1 through 6 and
from the built schemas for the rest; guardrails from each snapshot's
own `guardrails/`, the form that iteration was proven against, and
from the live use cases. `history/chain/` holds `schemas/`, `specs/`,
`revisions/`, `restrictions/`, and `retired/`, the five retired files
with their reasons. `RETIRED` becomes a list of (retired file, the
final set it must differ from) and no longer parses a directory name.

`successor_of` and the "revised" status are deleted (findings 7 and
the review's closing bug): with guardrails in flat per-use-case
folders the directory-is-an-iteration convention is gone, and the
function today misattributes three orders guardrails to reservations
successors, so they get no final-set check. Deleting it fixes that.

## Test cases

The corpus files keep their header and stay the project's variant of
the Cedar integration-tests format; the `--cedar-tests` export is what
the official `cedar run-tests` reads (finding 8). Two changes:

1. `reason` and `errors` name policies by their `@id` annotation, not
   by position (finding 9). The runner maps names to positions; the
   export maps them back; a test holds that every policy in every
   `policies.cedar` carries a unique `@id`, so the mapping can never
   silently misalign. The rewrite script touches the live use cases
   and hello only; the nine snapshots keep the positional format, and
   the history README says why the snapshot corpora and the live ones
   now differ (finding 10).
2. On a failure, `run-tests` prints the request on one line.

## History

```
history/
  README.md            what this is; the live code is elsewhere; why the corpora differ
  index.html           the timeline (today the root index.html)
  bola-reads/ … gateway/             nine snapshots, names unchanged, code and design.html together
  provable-composition.html          iteration 8's narrative, today analysis/design.html
  reservations-11.html … learning-path-15.html
  what-reservations-changed.html
  chain/               schemas/, specs/, revisions/, restrictions/, retired/
```

Nine snapshots, not ten: iteration 8 is the analysis crate (finding 16). The
snapshot names stay as they are so the moves are pure `git mv` and no
snapshot is edited except for two cross-snapshot paths in the gateway
snapshot's tests, which are listed in task 7. A link checker over
the tree and the anchors is written first in that task, because none
exists today (finding 15), and a smoke test runs every command line
in the learning pages.

## What is removed

Directories: `core` and the nine iteration directories
at the top level, folded into the layout above. Concepts a newcomer
meets: chains, revisions, restrictions, manifests, the word core, the
word token for a file, the "revised" status.

## Runs and tasks

Three overnight runs, not one (review, scope). Each task ends with
`./check.sh` green.

**Run 1, no behavior change.**

1. **Package skeleton.** Create `cedar_odcs/` with `engine/`, `cli/`,
   `gateway/`; move the Python modules; update `pyproject.toml`, the
   console script, `check.sh`, and every import. Fix the two
   hard-coded parent paths the move breaks, `REPO` in the command
   line and in its tests (finding 3); make the runner take the
   repository root as an argument rather than deriving it, so it is
   ready for `prove DIR`. The analysis crate and the bundled cvc5 stay
   where they are.
2. **Engine and interface split.** `engine/calls.py` as specified;
   handlers and command line call it; the agreement test. Depends on 1.

**Run 2, the use case shape.**

3. **Use case shape and proofs per use case**, one task, because the
   runner reads the guardrails by their old paths and cannot be green
   between the move and the rewrite (finding 1). Move each use case
   and hello into the shape; move guardrails beside their policies;
   rebase the build's output keys for `contract/`; give `prove DIR`
   its per-use-case mode and `prove-history` its chain mode with the
   tables' paths rewritten; move `history/chain/` contents out of the
   old analysis directory; delete `successor_of`. Depends on 2.
4. **Test case format.** Names for `reason` and `errors`; the unique
   `@id` test; the export mapping back; the failure printout. Depends on 3.
5. **The check command.** `check DIR` in order with the validate
   fallback; `check.sh` runs the engine's own tests, then `check` on
   `usecases/hello`, `usecases/orders`, `usecases/reservations`, then
   `prove-history`. Depends on 4.

**Run 3, history and words.**

6. **History.** Write the link checker and the command smoke test
   first. Move the nine snapshots and every narrative into
   `history/`; move the timeline; write the history README; update
   the two cross-snapshot paths in `gateway/test_interceptor.py` and
   the orders parity tests in `test_build.py` and
   `test_interceptor.py`; rewrite links; make the root `index.html` a
   landing page. Depends on 5.
7. **Docs.** Rewrite the README around the sentence, the shape, and
   the command; update the learning pages and the guide to the new
   paths and names; update the memory notes this project keeps.
   Depends on 6.
8. **Review.** A fresh reviewer reads the README, runs the three
   commands from a clean clone, and reports where the layout or the
   words lose them. Depends on 7.

**After the runs, its own task.**

9. **Non-vacuity**, reporting only, as stated above.

## Risks

- Task 3 is the largest change to the least familiar code, and it is
  the one task that cannot be split without a red intermediate state.
  The per-use-case mode is small; the chain mode is the existing
  runner with its paths rewritten.
- Link rewriting is wide; the link checker and the smoke test are
  written before the moves, not after.
- Hello's policies have never met the analysis. `prove usecases/hello`
  is never-errors plus zero guardrails; do not assume it passes.
- The cvc5 binary is ignored by git; it moves by hand on this machine,
  and the README's install path changes.

## Out of scope

`cedar-odcs new`, building from a plain fields file, an `add-case`
helper, YAML authoring of cases, CI, dropping the corpus header, and
any change to what the policies decide.
