// Guardrail: the support role grants no update permits. Proven by
// showing the policy set plus this forbid is equivalent to the policy
// set alone: the forbid forbids nothing that was allowed.
//
// The first version of this guardrail claimed more: "support may
// never update any order", with no ownership exception. The prover
// falsified it with a counterexample the corpus never sampled: a
// support member who personally owns the order, whom the ownership
// policy legitimately permits. The invariant that actually holds is
// that support members update only orders they own; the role itself
// grants nothing.
@id("guardrail-support-updates-only-as-owner")
forbid(
  principal in Role::"support",
  action == Action::"UpdateOrder",
  resource
) when {
  !(resource has owner && resource.owner == principal)
};
