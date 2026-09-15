# cedar-osdc

Data governance for agent tool calls, enforced with [Cedar](https://docs.cedarpolicy.com/) policies derived from [Open Data Contract Standard](https://bitol-io.github.io/open-data-contract-standard/) documents.

## Problem

Agents on AgentCore Runtime call upstream APIs through MCP tools registered in AgentCore Gateway. The tools authenticate with service credentials, so the APIs return whatever is asked for; the API layer itself has weak governance. Enforcement therefore lives in the agent stack, in Gateway interceptors on both the request and response legs of a tool call.

The threats covered, in OWASP API Security Top 10 terms: [API1 broken object level authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/) (BOLA), [API3 broken object property level authorization](https://owasp.org/API-Security/editions/2023/en/0xa3-broken-object-property-level-authorization/), and [API5 broken function level authorization](https://owasp.org/API-Security/editions/2023/en/0xa5-broken-function-level-authorization/) (BFLA).

## Approach

The project grows in small iterations, each one test-driven: test cases are added to a JSON corpus first, then the policies that make them pass. Cedar policies and test cases are engine-independent data, so the Python code used for learning and the eventual Rust enforcement build (a Lambda Runtime API proxy extension) run the same policies against the same corpus.

Design decisions and the full iteration plan are in the design document.

## Contents

Each iteration lives in its own directory with its policies, entities, test corpus, and a design document. `index.html` at the root indexes the iterations and links to each design document.

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
  - `tokens/*.json`: one hand-written token payload per mode, standing in for decoded tokens.
  - `claims.py`: `project`, the claims to Cedar request mapping (RFC 8693 `sub` and `act`), and `is_allowed` asked with a token.
  - `test_claims.py`: the three modes entered through their tokens; roles read from the token, not the store.
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
- `analysis/`: symbolic proofs over each iteration's policies, using Cedar's symbolic compiler and the cvc5 SMT solver. Spec equivalence, guardrail no-ops, and never-errors, proven over every possible request; findings and instructions in `analysis/README.md`.

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

## Onboarding questions

Each new use case is a tool, the API behind it, and the rules that govern it. The iterations define the requirement target; these questions, asked once per use case, say which patterns cover it and what is genuinely missing. Facts come from the token and the tool input first; lookups are added only for gaps the answers prove.

1. Identity: what bearer token reaches the Gateway? Whom does the subject identify (customer, employee, service)? Which claims are present: roles, tenant or account scoping, an `act` claim for acting on behalf of another party?
2. Verbs: which operations does the tool expose, and which are reads and which are writes? Writes are gated on the request leg before the call; reads are filtered on the response leg.
3. Rules and their facts: for each rule the use case needs, which facts decide it? Which of those are already in the token or the tool input, checkable with no lookup? Which are relationship facts, like order ownership, that live only in a system of record?
4. For the proven gaps: where does the fact come from (a claim added to the token, a pre-fetch through the read path, an entity store), and how fresh must it be?
5. Data contract: what does the response payload contain, field by field, and what classification level does each field carry? Fields outside the contract strip, so the contract must be complete before onboarding.
6. Grants: which roles hold which verbs, and which classification levels does each reader hold?

The identity questions double as a gap analysis. On behalf of access is in place but new, and today's claims may not carry everything the rules need to check. The corpus states the requirement target: each case names the facts its decision needs, so comparing today's tokens against the cases yields a concrete list of what exists, what is missing, and what must change in the identity setup before enforcement can rely on it. That list is an organizational change plan for data governance, tracked alongside the iterations.

## Iterations

1. Broken object level authorization (BOLA) on reads, done: object level checks, default deny.
2. BOLA on writes, done: the same ownership rule gated on the request leg; a denied write rejects the whole call.
3. Broken object property level authorization (API3) on reads, done: per-field decisions, strip denied fields from responses.
4. API3 on writes (mass assignment), done: per-field checks on write payloads; any denied field rejects the call whole.
5. Function level (API5), done: verbs held by roles; a verb held implies no other; the first role-granted write path.
6. On behalf of access modes, done: customer direct, employee direct, employee acting for a customer; the principal is the actor and the context carries the acted-for party.
7. ODCS as source of truth, done: Unity Catalog column tags to an ODCS contract to the tag maps and the Cedar schema, generated at build time and committed.
8. Provable composition: prove that combined policy sets preserve each iteration's guarantees, with equivalence and non-interference checks in CI. Per-iteration proofs already run in `analysis/`.
9. Row filtering for list endpoints.
10. Enforcement placement: move the checks into the Gateway interceptors.
