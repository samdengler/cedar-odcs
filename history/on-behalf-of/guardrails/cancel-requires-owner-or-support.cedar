// Guardrail, revised for mode: an order is cancelled by its owner, by
// an employee acting for its owner, or by support in direct mode.
@id("guardrail-cancel-requires-owner-or-support")
forbid(
  principal,
  action == Action::"CancelOrder",
  resource
) when {
  !(resource has owner &&
    resource.owner == (if context has actingFor then context.actingFor else principal)) &&
  !(!(context has actingFor) && principal in Role::"support")
};
