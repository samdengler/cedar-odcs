# analysis

Symbolic proofs over each iteration's policy set, and over the
composition of the iterations, using Cedar's symbolic compiler
([cedar-policy-symcc](https://crates.io/crates/cedar-policy-symcc))
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
- `on-behalf-of`: never errors (the `if context has actingFor then ...
  else principal` owner expression included); while acting for a
  party nothing is allowed outside that party's ownership, for every
  verb; acting reads only public and confidential fields and writes
  only owner fields. Four earlier guardrails that mention ownership or
  a role are revised for mode (`guardrails/on-behalf-of/`); the five
  mode-free ones are carried unchanged and reproven.
- `contract`: iteration 6's policies, unchanged, proven again against
  the schema iteration 7's build wrote from the data contract
  (`contract/generated/orders.cedarschema`, named in
  `SCHEMA_OVERRIDES`): the generated schema types the policies and
  admits the same twenty-four properties.
- Composition (iteration 8): each consecutive pair of iterations is
  preserved, given the declared revisions and within the declared
  restrictions; every guardrail ever written has a checked status
  against the final set. 90 proofs, 3 expected differences shown.

## Composition

The corpora carry each iteration's cases forward and rerun them; the
composition proofs state the same thing over every possible request.
Three kinds of check, all in `src/main.rs`:

- Preservation between consecutive iterations. Under the newer
  iteration's schema, for every request environment whose action the
  older iteration already had, the older and the newer policy sets
  are proven to decide identically. New actions have environments of
  their own and are left out, which is where non-interference comes
  for free: a policy for `RefundOrder` cannot change a `ReadOrder`
  decision because the two are proven in separate environments.
- Declared revisions. An iteration that changes an earlier decision
  on purpose declares the change as a policy file in `revisions/`.
  It is added to the older set before comparing, so the proof reads:
  the older iteration plus exactly these widenings equals the newer
  one. The runner also compares without the revisions and shows the
  difference, so a declared revision is visible rather than assumed.
- Restrictions. A forbid in `restrictions/` added to both sides
  confines the comparison to a region of the request space. Iteration
  6 promised no change in direct mode; `restrictions/direct-mode.cedar`
  forbids every request that carries `actingFor`, and the pair is
  proven equivalent over what remains.

The pairs and their results:

| Older | Newer | Declared revisions | Restriction | Actions compared |
|---|---|---|---|---|
| bola-reads | bola-writes | none | none | ReadOrder |
| bola-writes | field-reads | none | none | ReadOrder, UpdateOrder |
| field-reads | field-writes | none | none | ReadOrder, ReadOrderField, UpdateOrder |
| field-writes | function-level | support-updates-any-order, support-updates-support-fields | none | ReadOrder, ReadOrderField, UpdateOrder, UpdateOrderField |
| function-level | on-behalf-of | none | direct-mode | all six |
| on-behalf-of | contract | none | none | all six |

All six pairs are proven. The last pair changes no policy; it proves
that the schema generated from the data contract decides as the
hand-written one did. Without its declared revisions the
field-writes to function-level pair differs under `UpdateOrder`, shown
as expected.

The second pass puts every file under `guardrails/` against the final
policy set (`on-behalf-of`) and prints a status for each:

- carried: proven a no-op against the final set (twelve files, the
  five mode-free ones and the seven under `guardrails/on-behalf-of/`).
- revised: superseded by a file of the same name under a later
  iteration's guardrail directory, which is the one proven (four files:
  support-confidential, cancel-requires-owner-or-support,
  role-writes-only-role-fields, refund-implies-no-read).
- retired: listed in `RETIRED` with the iteration and reason, and shown
  to fail against the final set, so the retirement is a checked fact
  rather than a note (two files: support-never-updates and
  writes-require-ownership, both retired by iteration 5's role-granted
  update).

The runner's output for the composition section:

```
=== composition: preservation between iterations ===
  PASS  bola-reads preserved in bola-writes
        actions compared: Action::"ReadOrder"
  PASS  bola-writes preserved in field-reads
        actions compared: Action::"ReadOrder", Action::"UpdateOrder"
  PASS  field-reads preserved in field-writes
        actions compared: Action::"ReadOrder", Action::"ReadOrderField", Action::"UpdateOrder"
  PASS  field-writes preserved in function-level given the declared revision support-updates-any-order, support-updates-support-fields
        actions compared: Action::"ReadOrder", Action::"ReadOrderField", Action::"UpdateOrder", Action::"UpdateOrderField"
  SHOWN without the declared revision, field-writes and function-level differ: differs under Action::"UpdateOrder", as expected
  PASS  function-level preserved in on-behalf-of within direct-mode
        actions compared: Action::"CancelOrder", Action::"ReadOrder", Action::"ReadOrderField", Action::"RefundOrder", Action::"UpdateOrder", Action::"UpdateOrderField"
  PASS  on-behalf-of preserved in contract
        actions compared: Action::"CancelOrder", Action::"ReadOrder", Action::"ReadOrderField", Action::"RefundOrder", Action::"UpdateOrder", Action::"UpdateOrderField"

=== composition: every guardrail against the final set (on-behalf-of) ===
  SHOWN retired  guardrails/bola-writes/support-never-updates.cedar: iteration 5 granted the support role an object-level update: differs under Action::"UpdateOrder", as expected
  PASS  carried  guardrails/field-reads/fail-closed.cedar
  PASS  carried  guardrails/field-reads/restricted-unreadable.cedar
  revised guardrails/field-reads/support-confidential.cedar: superseded by guardrails/on-behalf-of/support-confidential.cedar
  ...
115 proved, 0 failed, 3 differences shown as expected
```

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
5. Iteration 5 widened earlier decisions in two places, and its design
   document declared one. The preservation proof with only the
   declared object-level update failed under `UpdateOrderField`, an
   action iteration 4 already had: the support field policy widens it
   for any writers map that names `support` as a writer. Iteration 4's
   map never did, so the carried corpus never sampled the change. The
   second widening is now declared in
   `revisions/function-level/support-updates-support-fields.cedar`,
   and the pair is proven with both. The corpus checks the map that
   exists; the proof checks every map.

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

Or, from the repository root, every check the repository has in one
command, tests first and then the proofs:

```sh
./check.sh
```

The runner uses the compiler's `CompiledPolicySet` and `CompiledPolicy`
API, which validates and compiles a policy set once per request
environment and reuses it across queries. The schemas in `schemas/`
are hand-written per iteration through iteration 6; from iteration 7
on, the schema is the one the contract build writes.
