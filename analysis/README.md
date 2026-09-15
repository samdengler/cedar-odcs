# analysis

Symbolic proofs over each iteration's policy set, in isolation, using
Cedar's symbolic compiler ([cedar-policy-symcc](https://crates.io/crates/cedar-policy-symcc))
and the cvc5 SMT solver. The corpus samples decisions by example; these
checks prove properties over every possible request. The compiler
itself is verified in Lean ([cedar-spec](https://github.com/cedar-policy/cedar-spec)),
so the proofs are trustworthy end to end.

## What is proved

Two kinds of properties, checked per iteration against the same
`policies.cedar` files the tests run:

- Spec equivalence. The policy set is decision-for-decision equivalent
  to a short behavioral spec (`specs/`). This proves both directions at
  once: everyone intended gets in, nobody else does.
- Guardrail no-ops. A forbid stating an invariant (`guardrails/`) is
  added to the policy set, and the combined set is proven equivalent to
  the original: the forbid forbids nothing that was allowed, so the
  invariant already held.

Plus never-errors for every policy, and the reveal: retyping each
policy under a schema where `owner` is optional (modeling a store that
may not know an order) makes Cedar's validator reject the unguarded
`resource.owner` accesses in the object-level policies, the same gap
the corpus pins as runtime evaluation errors. The guarded field
policies validate.

Current results, all proved:

- `bola-reads`: never errors; equivalent to "allowed exactly when owner
  or support".
- `bola-writes`: never errors; equivalent to "reads as iteration 1,
  updates for owners only"; the support role grants no updates.
- `field-reads`: never errors (the `has`/`hasTag` guards, proven);
  undeclared or unnamed fields fail closed; restricted fields are
  readable by nobody; support reaches confidential fields only through
  ownership, never through the role.
- `field-writes`: never errors; mass assignment fails closed for every
  field name; system fields are writable by nobody; writes require
  ownership (no role-granted write path); the four applicable earlier
  guardrails reproven.
- `function-level`: never errors; refund requires the finance role;
  cancel requires the owner or support; through the support role only
  fields whose writer is `support` are writable; the finance role
  grants no read. Two earlier guardrails are retired knowingly, because
  this iteration grants support an object-level update:
  support-never-updates and writes-require-ownership. The five that
  still apply are reproven.

## Findings

1. "Support may never update any order" is false, and the prover said
   so with a counterexample the corpus never sampled: a support member
   who personally owns the order, whom the ownership policy
   legitimately permits. The invariant that holds, now proven, is that
   the role grants nothing; ownership does. The corpus missed it
   because carol owns no orders.
2. Strict typing shapes guardrail style: the fail-closed condition must
   be written `!(context has field && ...hasTag(context.field))`. The
   De Morgan twin `!(context has field) || !...hasTag(context.field)`
   is rejected, because the typechecker's `has`-capability tracking
   follows `&&` but not `||`.
3. Role membership is not exclusive, again. Iteration 5's guardrail
   "finance reads only as owner" was falsified by a principal in both
   the finance and support roles, who reads through support. The
   invariant that holds is that the finance role grants no read; the
   forbid now excludes the support role too. Same lesson as finding 1,
   caught at build time.
4. Entity tags (`hasTag`/`getTag`) are fully supported by the symbolic
   compiler, which was this prototype's open fact-finding question. The
   tag proofs hold for every possible tag map, not just the one in
   `entities.json`.

## Running

Requires cvc5 1.3.1, which is not committed. Either put it on `PATH`,
set `CVC5` to the binary's absolute path, or drop it in `.tools/` where
the runner looks by default:

```sh
curl -sL -o cvc5.zip https://github.com/cvc5/cvc5/releases/download/cvc5-1.3.1/cvc5-macOS-arm64-static.zip
unzip -q cvc5.zip -d .tools && rm cvc5.zip
chmod +x .tools/cvc5-macOS-arm64-static/bin/cvc5
```

Then:

```sh
cargo run
```

The schemas in `schemas/` are hand-written per iteration until the
ODCS iteration generates them from the data contract. The planned
provable-composition iteration builds on this: proving that combined
policy sets preserve each iteration's guarantees (non-interference),
and that refactorings preserve behavior (equivalence of old and new).
