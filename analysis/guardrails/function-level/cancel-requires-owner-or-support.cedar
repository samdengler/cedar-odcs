// Guardrail: an order is cancelled only by its owner or by support.
// Finance holds refund, not cancel; a stranger holds nothing.
@id("guardrail-cancel-requires-owner-or-support")
forbid(
  principal,
  action == Action::"CancelOrder",
  resource
) when {
  !(resource has owner && resource.owner == principal) &&
  !(principal in Role::"support")
};
