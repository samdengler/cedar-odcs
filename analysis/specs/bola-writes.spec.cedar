// Behavioral spec for iteration 2: reads as in iteration 1, updates
// for owners only. Equivalence with the real policy set proves support
// and strangers can never update, and owners always can.
@id("spec-read-owner-or-support")
permit(
  principal,
  action == Action::"ReadOrder",
  resource
) when {
  (resource has owner && resource.owner == principal) ||
  principal in Role::"support"
};

@id("spec-update-owner-only")
permit(
  principal,
  action == Action::"UpdateOrder",
  resource
) when {
  resource has owner && resource.owner == principal
};
