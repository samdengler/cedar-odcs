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

## Running

Requires [uv](https://docs.astral.sh/uv/). From the repository root, this runs every iteration's test corpus:

```sh
uv run pytest -v
```

Each iteration is also a standalone uv project, so the same command works inside a single iteration directory, or from the root with `--project`:

```sh
uv run --project bola-reads pytest -v
```

## Iterations

1. Broken object level authorization (BOLA) on reads, done: object level checks, default deny.
2. BOLA on writes, done: the same ownership rule gated on the request leg; a denied write rejects the whole call.
3. Broken object property level authorization (API3) on reads, done: per-field decisions, strip denied fields from responses.
4. API3 on writes (mass assignment): per-field checks on write payloads, reject denied writes.
5. Function level (API5): actions permitted only to roles.
6. On behalf of access modes: customer direct, employee direct, employee acting for a customer.
7. ODCS as source of truth: generate the Cedar schema and field classifications from a data contract.
8. Row filtering for list endpoints.
9. Enforcement placement: move the checks into the Gateway interceptors.
