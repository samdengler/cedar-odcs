// Guardrail, revised for mode: the finance role grants no read. A
// finance member reads an order by owning it, by acting for its
// owner, or through the support role in direct mode.
@id("guardrail-refund-implies-no-read")
forbid(
  principal in Role::"finance",
  action == Action::"ReadOrder",
  resource
) when {
  !(resource has owner &&
    resource.owner == (if context has actingFor then context.actingFor else principal)) &&
  !(!(context has actingFor) && principal in Role::"support")
};
