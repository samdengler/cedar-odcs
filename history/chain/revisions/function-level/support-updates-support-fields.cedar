// Declared revision, found by the prover: iteration 5's design
// document declared one widening of earlier decisions, the object-
// level update for support. The preservation proof with only that
// revision failed under UpdateOrderField, an action iteration 4
// already had: the support field policy widens it too, for any
// writers map that names "support" as a writer. Iteration 4's map
// never did, so the carried corpus never sampled it. The text is P11
// of function-level/policies.cedar.
@id("support-updates-support-fields")
permit(
  principal in Role::"support",
  action == Action::"UpdateOrderField",
  resource
) when {
  context has field &&
  Contract::"Order/writers".hasTag(context.field) &&
  Contract::"Order/writers".getTag(context.field) == "support"
};
