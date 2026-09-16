// Guardrail: the finance role grants no read. A finance member reads
// an order only by owning it or through some other role that holds
// the verb. Verbs are granted one at a time; a role that holds one
// holds no other by implication.
//
// The first version of this guardrail claimed "finance reads only as
// owner". The prover falsified it with a principal in both the finance
// and support roles, who reads through support: role membership is
// not exclusive, the same lesson as iteration 2's support-never-
// updates. The invariant that holds is about the role, not the person.
@id("guardrail-refund-implies-no-read")
forbid(
  principal in Role::"finance",
  action == Action::"ReadOrder",
  resource
) when {
  !(resource has owner && resource.owner == principal) &&
  !(principal in Role::"support")
};
