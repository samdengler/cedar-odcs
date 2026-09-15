# How the proofs are used, and what they do not cover

The corpus samples decisions by example: it asks about alice and
order 1001 and says what the answer must be. The proofs in
`analysis/` ask about every possible request under a schema, every
possible entity store, and every possible tag map, and say what the
answer always is. This page is what that gives you, how the project
uses it, and where it stops.

## The two questions the prover answers

Cedar's symbolic compiler turns a policy set and a schema into a
formula, and an SMT solver decides questions about the formula. The
project asks two:

**Are these two policy sets equivalent?** For every request the
schema allows, do they decide the same? Every proof in the project is
this question, asked in different ways.

**Can this policy ever error?** An attribute read on an entity that
lacks it is an evaluation error, which Cedar treats as a deny. The
prover shows whether a policy is free of that for every input the
schema allows.

## How the project uses them

**Guardrail no-ops.** An invariant is written as a forbid, such as
"a restricted field is readable by nobody":

```cedar
@id("guardrail-restricted-unreadable")
forbid(
  principal,
  action == Action::"ReadOrderField",
  resource
) when {
  context has field &&
  Contract::"Order".hasTag(context.field) &&
  Contract::"Order".getTag(context.field) == "restricted"
};
```

The forbid is added to the policy set, and the combined set is proven
equivalent to the original. If it is, the forbid forbade nothing that
was allowed, so the invariant already held, for every request, every
store, and every tag map. If it is not, the prover returns the
request that breaks it, which is how the project found that "support
never updates" was false: a support member who owns the order.

**Spec equivalence.** For the early iterations, the policy set is
proven equivalent to a two-policy statement of what it should do.
This proves both directions at once: everyone intended gets in, and
nobody else.

**Preservation between iterations.** Each iteration is proven to
decide every action of the previous one identically, so growing the
policy set changed no earlier decision. Where an iteration changed a
decision on purpose, the change is declared as a policy file in
`analysis/revisions/`, and the proof reads: the old set plus exactly
these widenings equals the new. The runner also shows the difference
without the declared revision, so a revision is visible rather than
assumed. This is how the prover found that iteration 5 widened two
decisions where its document said one.

**Every guardrail's status.** Every guardrail file ever written is put
against the final policy set of its chain and given a status:
carried and proven, revised and superseded by a later file of the
same name, or retired and shown to fail. A retirement that
unexpectedly holds, or a carried guardrail that unexpectedly fails,
fails the run.

To run them: `uv run cedar-osdc prove`, with Rust and cvc5 installed
as `analysis/README.md` describes. The findings list there is the
record of what the prover caught that the tests had missed.

## What the proofs do not cover

Read this part before trusting a green run.

**They prove the policies, not the code that calls them.** The
handlers build entities from payloads, project a caller's token into
a principal, and copy presented facts into context. A proof says what
the policies decide given a request; it says nothing about whether
the request was built correctly. The critical review of this project
found its worst defects in exactly that layer, and every one of them
sat beside a green proof run.

**They assume the schema.** Every proof runs under a schema that says,
for instance, that an order always has an owner. The enforcement code
builds entities from payloads that may lack one. The runner's
"reveal" shows what happens when the schema admits a missing owner:
the validator rejects the unguarded policies of iterations 1 and 2.
The guarded ones pass. Write policies with `has` guards for this
reason.

**A guardrail can be vacuous.** A no-op proof shows the base set never
allows what the forbid names. The policies grant levels from
allowlists, so a forbid naming a level outside every allowlist passes
trivially. A guardrail with a misspelled level, `"restricetd"`, would
pass and prove nothing. There is no automatic check for this yet;
read a new guardrail against the corpus case it is meant to
generalize before trusting it.

**Declared revisions can absorb a mistake.** The process is: the
preservation proof fails, and the author writes a revision file. That
makes every change visible; it does not make every change right.
The revision file is where a reviewer should look.

**The verified part is the compiler.** Cedar's symbolic compiler is
verified in Lean against Cedar's semantics. The SMT solver, the
schemas and entity models the project wrote, and the enforcement code
are not. "Proven" in this project means: the policy set has this
property under this schema, as far as the compiler and the solver are
correct.

## What to do with this on your own use case

Write a guardrail for each sentence you would put in a governance
document: "nobody outside finance refunds", "a passport number is
readable by nobody". Put it under `analysis/guardrails/<usecase>/`,
add it to the iteration's list in `analysis/src/main.rs`, and run
`prove`. When it fails, read the counterexample: it is either a bug
in the policies or a sentence that was never true, and both are worth
knowing before a deployment.
