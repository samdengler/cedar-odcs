# cedar-osdc

Data governance for agent tool calls, enforced with [Cedar](https://docs.cedarpolicy.com/) policies derived from [Open Data Contract Standard](https://bitol-io.github.io/open-data-contract-standard/) documents.

## Problem

Agents on AgentCore Runtime call work APIs through MCP tools registered in AgentCore Gateway. The tools authenticate with service credentials, so the upstream APIs return whatever is asked for; the API layer itself has weak governance. Enforcement therefore lives in the agent stack, in Gateway interceptors on both the request and response legs of a tool call.

The threats covered, in OWASP API Security Top 10 terms: API1 broken object level authorization (BOLA), API3 broken object property level authorization, and API5 broken function level authorization (BFLA).

## Approach

The project grows in small iterations, each one test-driven: test cases are added to a JSON corpus first, then the policies that make them pass. Cedar policies and test cases are engine-independent data, so the Python code used for learning and the eventual Rust enforcement build (a Lambda Runtime API proxy extension) run the same policies against the same corpus.

Design decisions and the full iteration plan are in the design document.

## Contents

Each iteration lives in its own directory with its policies, entities, test corpus, and a design document. `index.html` at the root indexes the iterations and links to each design document.

- `bola-mvp/`: iteration 1. A standalone broken object level authorization (BOLA) slice with no AWS dependency.
  - `design.html`: the design narrative. Problem, where Cedar sits in the stack, Cedar concepts, walkthrough of the code, settled decisions, and open questions.
  - `policies.cedar`: two policies; everything else is default deny.
  - `entities.json`: the facts (users, a role, orders with owners).
  - `tests/bola.json`: six test cases in the [cedar-integration-tests](https://github.com/cedar-policy/cedar-integration-tests) corpus format.
  - `test_corpus.py`: pytest runner that feeds every corpus case to the engine.
  - `authorizer.py`: the enforcement-shaped wrapper, the same shape a Gateway interceptor will have.
- `field-filtering/`: iteration 2. Field filtering (API3) on top of the BOLA slice.
  - `design.html`: the design narrative. The second round of per-field questions, classification as entity facts, and the response-stripping wrapper.
  - `policies.cedar`: iteration 1's two policies carried forward, plus two field policies that check classification class membership.
  - `entities.json`: iteration 1's facts, plus `Field` entities grouped into `FieldClass` classes.
  - `tests/bola.json`: iteration 1's corpus, byte for byte, as a regression gate.
  - `tests/field-filtering.json`: twelve per-field cases, including the fail-closed ones.
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
uv run --project bola-mvp pytest -v
```

## Iterations

1. Broken object level authorization (BOLA), done: object level checks, default deny.
2. Broken object property level authorization (API3), done: per-field decisions, strip denied fields from responses.
3. Function level (API5): actions permitted only to roles.
4. On behalf of access modes: customer direct, employee direct, employee acting for a customer.
5. ODCS as source of truth: generate the Cedar schema and field classifications from a data contract.
6. Row filtering for list endpoints.
7. Enforcement placement: move the checks into the response interceptor.
