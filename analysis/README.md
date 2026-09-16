# analysis

Symbolic proofs over each iteration's policy set, and over the
composition of the iterations, using Cedar's symbolic compiler
([cedar-policy-symcc](https://crates.io/crates/cedar-policy-symcc))
and the cvc5 SMT solver. The corpus samples decisions by example; these
checks prove properties over every possible request. The compiler
itself is verified in Lean ([cedar-spec](https://github.com/cedar-policy/cedar-spec)).
The solver, the schemas and entity models written here, and the
enforcement code that builds requests are not; "What the proofs
assume" below says what a green run does and does not establish.

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
- `row-filtering`: proven against the same generated schema as
  `contract`; the list verb never errors; the twelve guardrails
  reproven against the thirteen-policy set, with acting-bounded-by-
  ownership revised to name the six order verbs, because the list
  call has no order to own and is allowed while acting.
- `orders` (the use case on core, iteration 11): iteration 9's
  policies under the schema core's build wrote; preserved from
  `row-filtering` with no revision; the twelve guardrails reproven.
- `reservations` (iteration 11): three possession policies never
  error; a lookup and a read require a presented pair; a pair reaches
  only the record it names; undeclared paths fail closed, nested ones
  included; restricted leaves are unreadable; possession reads public
  and confidential leaves only. Iteration 12 adds the writes: no write
  without a pair; possession writes only the record it names and only
  owner paths; mass assignment fails closed, nested paths included.
  Iteration 13 adds the specialist's view: lookup, read, and writes
  require a pair or a specialist (three guardrails revised, the bare
  ones retired and shown to fail); internal leaves and specialist paths
  are off while a pair is presented; without a pair a specialist
  writes specialist paths only; listing requires a specialist; a human
  outside the employee role is granted nothing on any verb.
- Composition (iteration 8): each consecutive pair of iterations is
  preserved, given the declared revisions and within the declared
  restrictions; every guardrail ever written has a checked status
  against the final set. 141 proofs, 3 expected differences shown.

## Composition

The corpora carry each iteration's cases forward and rerun them; the
composition proofs state the same thing over every possible request.
Three kinds of check, all in `src/main.rs`:

- Preservation between consecutive iterations. Under the newer
  iteration's schema, for every request environment whose action the
  older iteration already had, the older and the newer policy sets
  are proven to decide identically. New actions have environments of
  their own and are left out, and non-interference follows
  without a separate proof: a policy for `RefundOrder` cannot change a `ReadOrder`
  decision because the two are proven in separate environments.
- Declared revisions. An iteration that changes an earlier decision
  on purpose declares the change as a policy file in `revisions/`.
  It is added to the older set before comparing, so the proof reads:
  the older iteration plus these widenings equals the newer
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
| contract | row-filtering | anyone-lists-orders | none | all seven |
| row-filtering | orders | none | none | all seven |

All eight pairs are proven. Iterations belong to chains (`orders`,
`reservations`); pairs and the guardrail status pass run per chain,
each against that chain's final set. The contract pair changes no policy; it
proves that the schema generated from the data contract decides as
the hand-written one did. The two share that generated schema, which
declares the list verb, so iteration 9's one permit is a declared
revision on it and the six order actions are proven untouched. Without its declared revisions the
field-writes to function-level pair differs under `UpdateOrder`, shown
as expected.

The second pass puts every file under `guardrails/` against the final
policy set (`row-filtering`) and prints a status for each:

- carried: proven a no-op against the final set (twelve files, the
  five mode-free ones, six under `guardrails/on-behalf-of/`, and the
  one under `guardrails/row-filtering/`).
- revised: superseded by a file of the same name under a later
  iteration's guardrail directory, which is the one proven (five files:
  support-confidential, cancel-requires-owner-or-support,
  role-writes-only-role-fields, refund-implies-no-read, and iteration
  6's acting-bounded-by-ownership, revised by iteration 9 to name the
  order verbs).
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
  PASS  contract preserved in row-filtering
        actions compared: Action::"CancelOrder", Action::"ReadOrder", Action::"ReadOrderField", Action::"RefundOrder", Action::"UpdateOrder", Action::"UpdateOrderField"

=== composition: every guardrail against the final set (row-filtering) ===
  SHOWN retired  guardrails/bola-writes/support-never-updates.cedar: iteration 5 granted the support role an object-level update: differs under Action::"UpdateOrder", as expected
  PASS  carried  guardrails/field-reads/fail-closed.cedar
  PASS  carried  guardrails/field-reads/restricted-unreadable.cedar
  revised guardrails/field-reads/support-confidential.cedar: superseded by guardrails/on-behalf-of/support-confidential.cedar
  ...
208 proved, 0 failed, 7 differences shown as expected
```

## What the proofs assume

A proof here is a statement about a policy set under a schema, as far
as the symbolic compiler and cvc5 are correct. Three things sit
outside it, and the enforcement code in `cedar_osdc/engine/` is responsible for
them:

1. The schema's attributes are present. Every proof runs under a
   schema that says, for instance, that an order always has an owner.
   The response leg builds entities from payloads that may lack one;
   the reveal below shows the unguarded policies of iterations 1 and
   2 failing validation when the schema admits a missing owner, and
   the guarded policies passing. Guard attribute reads with `has`.
2. Entities are well formed. The tag maps are data the contract build
   wrote; a proof holds for every possible map, which is a strength,
   and says nothing about whether the deployed map is the intended
   one.
3. The request was built correctly. Which token became which
   principal, which tool argument became which presented fact, which
   payload field became which attribute: the projection and the
   handlers decide these, and no proof reaches them. The critical
   review of this project found its worst defects in that layer,
   beside a green proof run.

Two limits of the method itself. A guardrail no-op proves the base set
never allows what the forbid names, so a forbid naming a level outside
every allowlist, a misspelled one say, passes trivially; there is no
vacuity check yet, and a new guardrail should be read against the
corpus case it generalizes. And a declared revision makes a change
visible rather than right; the revision file is where a reviewer
should look.

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
   tag proofs hold for every possible tag map, including every map other than
   the one in `entities.json`.
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

6. A guardrail over two verbs with a disjunction is two guardrails.
   Iteration 13's "specialist view off with a pair" joined the read
   condition (an internal leaf) and the write condition (a specialist
   path) in one forbid over both field verbs; the prover refused it,
   because the disjunction also forbade a possession read of a public
   leaf whose writer is the specialist. Split per verb, both hold.

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
on, the schema is the one the contract build writes, named in
`SCHEMA_OVERRIDES`.
