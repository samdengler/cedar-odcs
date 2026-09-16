# Reorganization plan

A plan for review, then tasks, then an overnight run. It covers the
repository layout, the shape of a use case, the split of the tool
into an engine and two interfaces, proofs per use case, and the test
case format. Nothing here changes what the policies decide; every
check that is green before the work is green after it.

## The sentence

A use case is a folder with four things, a data contract, policies,
tests, and guardrails; one command checks the folder; the same folder
is what the Gateway loads.

## Target layout

```
README.md
cedar_osdc/      the tool: engine, command line, Gateway handlers, proof runner
usecases/        one folder per domain
learn/           the path and the guide
designs/         plans and designs for work not yet done, this document among them
history/         how it was built: iterations 1 through 10 and every design narrative
```

Five directories a newcomer meets, each named for what it holds. The
top level today has seventeen.

## The shape of a use case

```
usecases/reservations/
  contract/            the catalog export and everything generated from it
    unity/             the table and its column tags, as Unity Catalog returns them
    reservation.odcs.yaml
    generated/         the tag maps and the Cedar schema
  policies.cedar
  guardrails/          invariants: forbids that must change nothing
  tests/
    test-cases/        request in, decision expected; every JSON file here runs
    identities/        who can call: the claims of each, one file per identity
    responses/         what the API returns, saved, one file per response
  facts.json           sample users, roles, and records the tests refer to
  entities.json        facts plus the generated maps, built, committed
  usecase.py           the descriptor: entity type, attributes, verbs, tool table
```

The same shape for hello, orders, reservations, and a new domain.
Identities and responses are fixtures, data the engine reads as it
would read the real thing. The one mock in a use case is the fetch
function in the descriptor, which reads a saved response instead of
calling the API, and is replaced by a real read at deployment.

## One command

```sh
cedar-osdc check usecases/reservations
```

Runs, in order, stopping at the first failure:

1. `build`: catalog to contract to maps and schema; fails on an unclassified column.
2. `validate`: the policies against the built schema, through the official `cedar` command when it is installed, otherwise through the proof runner's validator.
3. `run-tests`: every file under `tests/test-cases/`.
4. `prove`: every file under `guardrails/`, plus never-errors for every policy.

The four stay callable one at a time. `dry-run`, `check-access`, and
`share` stay for asking questions. `new` stays deferred; the guide
says to copy hello.

## The tool: one package, an engine and two interfaces

```
cedar_osdc/
  engine/
    contract.py      the build: Unity Catalog to ODCS to maps and schema
    identities.py    the projection from claims to the Cedar parties (today claims.py)
    calls.py         a tool call to a decision: verb, record, presented facts, payload, both legs
    enforce.py       the two legs by path, the pre-fetch, entities from payloads
    usecase.py       the descriptor
    corpus.py        the test case runner
  cli/
    main.py          arguments in, words out
  gateway/
    handlers.py      interceptor events in, Gateway results out; bearer decoding
    lambda.py        the two Lambda entry points, loading a use case by name
  prover/
    Cargo.toml, src/ the Rust runner (today analysis/)
```

The line: the engine owns everything that decides, including the
meaning of a tool call, which today sits in the handler file and is
reached by the command line through private methods. The interfaces
own translation only. A test holds them to it: for every fixture
event in every use case, the Gateway handler and the dry run agree.

The Rust runner lives inside the package directory so the top level
stays at five; cargo does not care where its crate sits. The
bundled cvc5 moves with it.

## Proofs per use case

Everything that states what must be true of a use case lives in the
use case; only the runner is shared.

- `guardrails/*.cedar`: every file applies to the folder's current
  policies. No manifest. Retiring a guardrail is deleting the file,
  which git records.
- `prove DIR` proves: each guardrail is a no-op against the policies;
  no policy can error under the built schema; and each guardrail is
  not vacuous, meaning the forbid on its own is satisfiable under the
  schema, so a misspelled level cannot pass silently. The third is
  new; the proofs page asks for it.
- The chain of iterations 1 through 10, with its pairs, declared
  revisions, restrictions, and retirements, is a fact about history.
  It moves to `history/` with the snapshots, keeps its tables, and
  runs as `prove-history`, which `check.sh` calls. It is not part of a
  use case and a newcomer never meets it.
- The two behavioral specs of iterations 1 and 2 stay in history.

## Test cases

The format stays the Cedar project's, so Cedar's tools read it and
`share` opens a case in the playground. Three changes:

1. `reason` names policies by their `@id` annotation, not by position.
   The runner maps names to positions; a reordered policy file breaks
   nothing. Every existing case is rewritten by script.
2. The per-file header goes. Every file runs against the folder's
   `policies.cedar` and `entities.json`.
3. On a failure, `run-tests` prints the request on one line, so nobody
   opens the JSON to see what was asked.

`run-tests --cedar-tests` keeps writing the official format for the
`cedar` command.

## History

`history/` holds iterations 1 through 10 as they were built, each a
standalone project that still runs, and every design narrative:

```
history/
  README.md            what this is, and that the live code is elsewhere
  index.html           the timeline (today the root index.html)
  01-bola-reads/ … 10-gateway/      the snapshots, code and design.html together
  11-reservations.html … 15-learning-path.html
  what-reservations-changed.html
  chain/               the proof chain's revisions, restrictions, specs, and the retired guardrails
```

Links inside the narratives are rewritten by script and checked by
the anchor test used when they were written. The orders use case's
parity tests point at the snapshots' new paths.

## What is removed

Directories: `core`, `analysis`, `contract`, `row-filtering`,
`gateway`, and the seven other iteration directories, all folded into
the five above. Concepts a newcomer meets: chains, revisions,
restrictions, manifests, the word core, the word token for a file.

## Tasks, in order

Each task ends with `./check.sh` green. Dependencies are noted.

1. **Package skeleton.** Create `cedar_osdc/` with `engine/`, `cli/`,
   `gateway/`, `prover/`; move the Python modules and the Rust crate;
   update `pyproject.toml`, the console script, `check.sh`, and every
   import. No behavior change.
2. **Engine and interface split.** Extract the tool call mapping from
   the handlers into `engine/calls.py`; make the handlers and the
   command line call it; add the agreement test across every fixture
   event. Depends on 1.
3. **Use case shape.** Move each use case, and hello, into the folder
   shape: `contract/`, `guardrails/`, `tests/test-cases/`,
   `tests/identities/`, `tests/responses/`. Move guardrails from the
   analysis directory beside their policies. Update the descriptor
   loader, the build, and every test path. Depends on 1.
4. **Test case format.** Reasons by name; header removed; failure
   printout. Rewrite every case file by script; keep the export.
   Depends on 3.
5. **Prover per use case.** The runner takes a use case directory,
   reads `guardrails/`, proves no-ops, never-errors, and non-vacuity;
   `prove-history` runs the chain from `history/chain/`. Depends on 3.
6. **The check command.** `check DIR` running build, validate,
   run-tests, prove in order; `check.sh` loops over use cases and runs
   the engine's own tests and `prove-history`. Depends on 4 and 5.
7. **History.** Move the ten snapshots and every narrative into
   `history/`; rewrite links; move the timeline; write the history
   README. Update the orders parity tests. Depends on 3.
8. **Docs.** Rewrite the README around the sentence, the shape, and
   the command; update the learning pages and the guide to the new
   paths and names; update the memory notes this project keeps.
   Depends on 6 and 7.
9. **Review.** A fresh reviewer reads the README, runs the three
   commands from a clean clone, and reports where the layout or the
   words lose them. Depends on 8.

Tasks 2, 3, and 5 are the substantive ones; the rest are moves and
rewrites gated by the checks.

## Risks

- The runner rewrite in task 5 is the largest change to the least
  familiar code. The existing tables become the history chain's
  input; the per-use-case mode is new and small.
- Link rewriting across fifteen narratives and the learning pages is
  mechanical but wide; the anchor test catches broken fragments, and
  a link checker over the tree catches broken files.
- The cvc5 binary is ignored by git and sits in the analysis
  directory; it moves by hand on this machine, and the README's
  install path changes.
- Git history follows the files under `git mv`; blame across the
  move survives.

## Out of scope

`cedar-osdc new`, building from a plain fields file, an `add-case`
helper, YAML authoring of cases, CI, and any change to what the
policies decide.
