// Guardrail: a field request with no field named, or naming a field
// missing from the contract's tag map, is never allowed. The
// fail-closed invariant as a theorem, for every field name at once.
@id("guardrail-fail-closed")
forbid(
  principal,
  action == Action::"ReadEmployeeField",
  resource
) when {
  !(context has field && Contract::"Employee".hasTag(context.field))
};
