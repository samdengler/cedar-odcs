# cedar-osdc

Data governance for agent tool calls, enforced with [Cedar](https://docs.cedarpolicy.com/) policies derived from [Open Data Contract Standard](https://bitol-io.github.io/open-data-contract-standard/) documents.

## Start here

Clone, then from the repository root with [uv](https://docs.astral.sh/uv/) installed:

```sh
uv sync
uv run cedar-osdc run-tests usecases/hello
uv run cedar-osdc check-access usecases/hello --caller usecases/hello/tests/identities/ada.json
```

Then follow the [learning path](learn/README.md): three steps that begin where Cedar's own tutorial ends, each a use case you can run, change, and break. The [guide](learn/guide.md) says what to know about your own domain to fill in a use case, and the [proofs page](learn/proofs.md) says what the symbolic proofs give and do not. The rest of this README is the map of the repository and the record of how it was built.

## Problem

Agents on AgentCore Runtime call upstream APIs through MCP tools registered in AgentCore Gateway. The tools authenticate with service credentials, so the APIs return whatever is asked for; the API layer itself has weak governance. Enforcement therefore lives in the agent stack, in Gateway interceptors on both the request and response legs of a tool call.

The threats covered, in OWASP API Security Top 10 terms: [API1 broken object level authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/) (BOLA), [API3 broken object property level authorization](https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/), and [API5 broken function level authorization](https://owasp.org/API-Security/editions/2023/en/0xa5-broken-function-level-authorization/) (BFLA).

## Approach

The project grows in small iterations, each one test-driven: test cases are added to a JSON corpus first, then the policies that make them pass. Cedar policies and test cases are engine-independent data, so the Python code used for learning, the Gateway interceptor handlers, and any later Rust build run the same policies against the same corpus.

Design decisions and the full iteration plan are in the design document.

## Contents

Iterations 1 through 10 live in their own directories with policies, entities, test corpus, and a design document; from iteration 11 the mechanism lives in `core/` and each use case in `usecases/`. `index.html` at the root indexes the iterations and links to each design document.

- `bola-reads/`: iteration 1. Broken object level authorization (BOLA) on reads, standalone with no AWS dependency.
  - `design.html`: the design narrative. Problem, where Cedar sits in the stack, Cedar concepts, walkthrough of the code, settled decisions, and open questions.
  - `policies.cedar`: two policies; everything else is default deny.
  - `entities.json`: the facts (users, a role, orders with owners).
  - `tests/bola.json`: six test cases in the [cedar-integration-tests](https://github.com/cedar-policy/cedar-integration-tests) corpus format.
  - `test_corpus.py`: pytest runner that feeds every corpus case to the engine.
  - `authorizer.py`: the enforcement wrapper; it does the same job a Gateway interceptor will do.
- `bola-writes/`: iteration 2. BOLA on writes: the same ownership rule gated on the request leg.
  - `design.html`: the design narrative. Why writes are gated before the call, reject instead of strip, and where the ownership fact comes from pre-flight.
  - `policies.cedar`: iteration 1's two policies, plus one `UpdateOrder` policy.
  - `entities.json`: iteration 1's facts, unchanged.
  - `tests/bola.json`: iteration 1's corpus, carried as a regression gate.
  - `tests/bola-writes.json`: six object-level write cases.
  - `test_corpus.py`: the same runner as iteration 1.
  - `authorizer.py`: the request-leg gate; forward on Allow, reject the whole call on Deny.
- `field-reads/`: iteration 3. Field filtering (API3 reads) on top of iterations 1 and 2.
  - `design.html`: the design narrative. The second round of per-field questions, classification as entity tags, and the response-stripping wrapper.
  - `policies.cedar`: the three object-level policies carried forward, plus two field policies that look fields up in the classification map.
  - `entities.json`: iteration 1's facts, plus the classification map as entity tags on a `Contract` entity.
  - `tests/bola.json`, `tests/bola-writes.json`: iterations 1 and 2's corpora, byte for byte, as a regression gate.
  - `tests/field-reads.json`: twelve per-field cases, including the fail-closed ones.
  - `test_corpus.py`: the same runner as iteration 1.
  - `field_filter.py`: `is_allowed` with context, plus `filter_response`, the response-leg wrapper that strips denied fields and reports the removals.
  - `test_filter.py`: one upstream payload filtered end to end for each caller.
- `field-writes/`: iteration 4. Mass assignment defense (API3 writes) on top of iterations 1 through 3.
  - `design.html`: the design narrative. The payload round on the request leg, the writers map, and whole-call rejection.
  - `policies.cedar`: the five prior policies carried forward, plus one write-field policy.
  - `entities.json`: the prior facts, plus the writers map as entity tags on a second `Contract` entity.
  - `tests/bola.json`, `tests/bola-writes.json`, `tests/field-reads.json`: iterations 1 through 3's corpora, byte for byte, as a regression gate.
  - `tests/field-writes.json`: eleven write-field cases, including mass assignment failing closed.
  - `test_corpus.py`: the same runner.
  - `write_gate.py`: `check_request`, which rejects a payload whole when any field is denied and names the denied fields.
  - `test_gate.py`: whole-call rejection pinned end to end.
- `function-level/`: iteration 5. Function level authorization (API5) on top of iterations 1 through 4.
  - `design.html`: the design narrative. Roles hold verbs, the role-granted write path, and the first revised corpus case.
  - `policies.cedar`: the six prior policies carried forward, plus five verb and role policies.
  - `entities.json`: the prior facts, plus a finance role and a member of it; the writer of `internalNotes` becomes `support`.
  - `tests/bola.json`, `tests/field-reads.json`, `tests/field-writes.json`: carried byte for byte. `tests/bola-writes.json`: carried with one case revised, support's object-level update, now Allow.
  - `tests/function-level.json`: fourteen verb cases, including every cross-verb attempt.
  - `test_corpus.py`: the same runner.
  - `request_gate.py`: `check_call`, the whole request leg: the verb round, then the payload round for updates.
  - `test_gate.py`: verb rejection before the payload is read; role-granted updates bounded by the writers map.
- `on-behalf-of/`: iteration 6. On behalf of access modes on top of iterations 1 through 5.
  - `design.html`: the design narrative. Three modes and one principal, every policy given a mode, and the claims the corpus needs, each marked assumed until confirmed.
  - `policies.cedar`: the eleven prior policies, each revised for mode, plus one forbid: only employees act for others.
  - `entities.json`: the prior facts, plus an employee role that support and finance belong to.
  - `tests/bola.json` through `tests/function-level.json`: iterations 1 through 5's corpora, byte for byte; every carried case is direct mode.
  - `tests/on-behalf-of.json`: fifteen cases across the three modes.
  - `callers/*.json`: one hand-written token payload per mode, standing in for decoded callers.
  - `claims.py`: `project`, the claims to Cedar request mapping (RFC 8693 `sub` and `act`), and `is_allowed` asked with a token.
  - `test_claims.py`: the three modes entered through their callers; roles read from the token.
- `contract/`: iteration 7. ODCS as source of truth: the tag maps and the Cedar schema generated at build time.
  - `design.html`: the design narrative. The two-stage build, the Unity Catalog tag convention, and what the contract does and does not decide.
  - `unity/`: recorded Unity Catalog API responses, the tables endpoint and the entity tag assignments endpoint, standing in for live calls.
  - `unity_import.py`: stage one, catalog to contract. An unclassified column fails the build.
  - `order.odcs.yaml`: the generated ODCS v3.2.0 document, committed.
  - `generate.py`: stage two, contract to the classification map, the writers map, and the resource entity declaration.
  - `build.py`: both stages; assembles `entities.json` from `facts.json` and the generated maps, and `generated/orders.cedarschema` from the hand-written principal and action fragments and the generated entity declarations.
  - `policies.cedar`: iteration 6's file, unchanged.
  - `tests/*.json`: iterations 1 through 6's corpora, byte for byte, plus `tests/contract.json`: five cases about the generated maps.
  - `test_build.py`: committed artifacts are current; the contract validates; iteration 6's map entries are carried; the generated schema equals the hand-written one; an incomplete catalog fails the build.
- `row-filtering/`: iteration 9. Row filtering for list endpoints on top of iterations 1 through 7.
  - `design.html`: the design narrative. Listing decides nothing, rows are authorized one by one, and resource entities come from the payload.
  - `policies.cedar`: iteration 6's twelve policies, plus one list verb anyone may call.
  - `entities.json`: iteration 7's build output, unchanged.
  - `tests/*.json`: iterations 1 through 7's corpora, byte for byte, plus `tests/row-filtering.json`: six list verb cases.
  - `row_filter.py`: `filter_rows`, the response leg for a list: one `ReadOrder` per row built from the row itself, then the per-field round on each surviving row.
  - `test_rows.py`: the rows and fields each caller and mode receives; a row without a usable id dropped; a row without an owner decided without ownership.
- `gateway/`: iteration 10. Enforcement in AgentCore Gateway interceptors.
  - `design.html`: the design narrative. The two interception points, the handlers, where the native policy engine fits, and the Lambda extension decision revisited.
  - `interceptor.py`: `request_handler` and `response_handler`, the Gateway's event and result formats for MCP targets, and the tool table.
  - `enforce.py`: the wrappers of iterations 3, 5, and 9, asked with a token's projection.
  - `bearer.py`: iteration 6's projection, plus decoding of the forwarded bearer token.
  - `policies.cedar`, `entities.json`: iteration 9's policies and iteration 7's build output, byte for byte; a test says so.
  - `events/*.json`: fifteen Gateway events in the documented shapes, one response per tool.
  - `tests/*.json`: every prior corpus, carried. `test_interceptor.py`: the handlers driven by the events.
- `learn/`: iteration 15. The learning path (`README.md`), the hello use case (`hello/`), steps 2 and 3 (`roles.md`, `possession.md`), the guide (`guide.md`), and the proofs page (`proofs.md`).
- `core/`: the mechanism from iteration 11 on, with no use case named in it: the descriptor, the claims projection, the two legs of enforcement by path, the Gateway handlers, the contract build with nested columns, and the corpus runner. Its own `README.md` lists the modules; `what-reservations-changed.html` is the writeup of what the reservation use case changed in it; `cli.py` is the `cedar-osdc` command and `iteration-14.html` its design narrative.
- `usecases/orders/`: iteration 9's policies and iteration 7's contract sources on core, every corpus and Gateway fixture carried, at parity with the numbered iterations.
- `usecases/reservations/`: iteration 11. A reservation is held by whoever presents its record locator and the holder's last name.
  - `iteration-11.html`: the design narrative. Possession in context, two legs with one credential, nested records by path, and the core split.
  - `unity/`: a reservations table with struct and array columns, and path-scoped tag assignments.
  - `reservation.odcs.yaml`, `generated/`, `entities.json`: the build's outputs, committed.
  - `iteration-12.html`: writes by possession and the pre-fetch before a write.
  - `iteration-13.html`: the specialist's view, the agent as a principal, and the list.
  - `policies.cedar`: six possession policies, seven specialist policies, and one forbid: only employees are acted for.
  - `records.json`: the read path's stand-in for the pre-fetch. `callers.json`, `callers/`: the three caller shapes.
  - `tests/*.json`: forty-three cases. `events/`: twenty-four Gateway fixtures.
  - `usecase.py`, `test_build.py`, `test_interceptor.py`, `test_corpus.py`.
- `analysis/`: iteration 8 and the proofs behind every iteration, using Cedar's symbolic compiler and the cvc5 SMT solver. Per iteration: spec equivalence, guardrail no-ops, and never-errors, proven over every possible request. Across iterations: each policy set proven to preserve its predecessor's decisions, with revisions declared as data and the on behalf of comparison restricted to direct mode, and every guardrail's status (carried, revised, retired) checked against the final set. Findings and instructions in `analysis/README.md`; the design narrative in `analysis/design.html`.

## Command line

Requires [uv](https://docs.astral.sh/uv/). From the repository root, `uv sync` installs the `cedar-osdc` command, which runs the mechanism against a use case directory:

```sh
uv run cedar-osdc run-tests usecases/reservations
uv run cedar-osdc check-access usecases/reservations --caller usecases/reservations/callers/agent.json --presented locator=ABC123 --presented lastName=Smith
uv run cedar-osdc dry-run usecases/reservations --caller usecases/reservations/callers/agent.json --tool reservations___get_reservation --arg recordLocator=ABC123 --arg lastName=Smith --response usecases/reservations/records/ABC123.json
uv run cedar-osdc share usecases/reservations --case "co-traveler"
```

The verbs match the official `cedar` command where the meaning is the same (`authorize`, `validate`, `run-tests`) and add `dry-run`, one tool call through both legs without calling the tool, and `check-access`, what a caller may do. `share` opens any case in Cedar's playground. `build`, `validate`, and `prove` run the contract build, the official validator, and the proofs. A caller file is a JSON object of claims; `usecases/reservations/callers.json` holds three to copy from. The design narrative is `cedar_osdc/iteration-14.html`.

## Running

Requires [uv](https://docs.astral.sh/uv/). From the repository root, this runs every iteration's test corpus and iteration 7's build tests:

```sh
uv run pytest -v
```

Each iteration is also a standalone uv project, so the same command works inside a single iteration directory, or from the root with `--project`:

```sh
uv run --project bola-reads pytest -v
```

The symbolic proofs run separately; they need Rust and the cvc5 solver (see `analysis/README.md`):

```sh
cd analysis && cargo run
```

Both together, every test and every proof, from the repository root:

```sh
./check.sh
```

## Onboarding questions

Each new use case is a tool, the API behind it, and the rules that govern it. The iterations define the requirement target; these questions, asked once per use case, say which patterns cover it and what is genuinely missing. Facts come from the token and the tool input first; lookups are added only for gaps the answers prove.

1. Identity: what bearer token reaches the Gateway? Whom does the subject identify (customer, employee, service)? Which claims are present: roles, tenant or account scoping, an `act` claim for acting on behalf of another party?
2. Verbs: which operations does the tool expose, and which are reads and which are writes? Writes are gated on the request leg before the call; reads are filtered on the response leg.
3. Rules and their facts: for each rule the use case needs, which facts decide it? Which of those are already in the token or the tool input, checkable with no lookup? Which are relationship facts, like order ownership, that live only in a system of record?
4. For the proven gaps: where does the fact come from (a claim added to the token, a pre-fetch through the read path, an entity store), and how fresh must it be?
5. Data contract: what does the response payload contain, field by field, and what classification level does each field carry? Fields outside the contract strip, so the contract must be complete before onboarding.
6. Grants: which roles hold which verbs, and which classification levels does each reader hold?

The identity questions double as a gap analysis. On behalf of access is in place but new, and today's claims may not carry everything the rules need to check. The corpus states the requirement target: each case names the facts its decision needs, so comparing today's callers against the cases yields a concrete list of what exists, what is missing, and what must change in the identity setup before enforcement can rely on it. That list is an organizational change plan for data governance, tracked alongside the iterations.

## Iterations

1. Broken object level authorization (BOLA) on reads, done: object level checks, default deny.
2. BOLA on writes, done: the same ownership rule gated on the request leg; a denied write rejects the whole call.
3. Broken object property level authorization (API3) on reads, done: per-field decisions, strip denied fields from responses.
4. API3 on writes (mass assignment), done: per-field checks on write payloads; any denied field rejects the call whole.
5. Function level (API5), done: verbs held by roles; a verb held implies no other; the first role-granted write path.
6. On behalf of access modes, done: customer direct, employee direct, employee acting for a customer; the principal is the actor and the context carries the acted-for party.
7. ODCS as source of truth, done: Unity Catalog column tags to an ODCS contract to the tag maps and the Cedar schema, generated at build time and committed.
8. Provable composition, done: each iteration proven to preserve its predecessor's decisions, revisions declared as data, every guardrail's status checked against the final set; `./check.sh` runs every test and proof.
9. Row filtering, done: list endpoints return only the rows the caller may read, each reduced to the fields they may read.
10. Enforcement placement, done: the request and response legs as Gateway interceptor handlers, tested against the documented event shapes; deployment to an account is a later step.
11. Reservations by locator and last name, done: a second use case with no customer identity, possession decided on the response leg, nested records by path, the mechanism extracted into `core/`.
12. Writes by possession, done: contact, seats, and cancellation by whoever holds the pair; the record is fetched through the read path before a write is forwarded.
13. The specialist, the agent, and the list, done: the agent as a principal of its own type, the specialist as the acted-for human whose roles decide, the specialist's view on without a pair and off with one, listing for specialists only.
14. The command line, done: nine verbs matching Cedar's where the meaning is the same, a dry run of one tool call, a report of what a caller may do, and a link into Cedar's playground for any case.
15. The learning path, done: three runnable steps after Cedar's own tutorial, the guide, the proofs page, and caller files in every use case.