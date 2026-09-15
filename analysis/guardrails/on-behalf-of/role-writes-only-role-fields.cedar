// Guardrail, revised for mode: outside ownership (own or acted-for),
// a support agent writes only fields whose writer is "support", and
// only in direct mode.
@id("guardrail-role-writes-only-role-fields")
forbid(
  principal in Role::"support",
  action == Action::"UpdateOrderField",
  resource
) when {
  !(resource has owner &&
    resource.owner == (if context has actingFor then context.actingFor else principal)) &&
  !(!(context has actingFor) &&
    context has field &&
    Contract::"Order/writers".hasTag(context.field) &&
    Contract::"Order/writers".getTag(context.field) == "support")
};
