// Guardrail: a write naming no field, or naming a field missing from
// the writers map, is never allowed. The mass assignment defense as a
// theorem, for every field name at once (isAdmin, debugTrace, ...).
@id("guardrail-mass-assignment-fail-closed")
forbid(
  principal,
  action == Action::"UpdateOrderField",
  resource
) when {
  !(context has field && Contract::"Order/writers".hasTag(context.field))
};
