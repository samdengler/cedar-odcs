// Guardrail: a write naming no field, or naming a field missing from
// the writers map, is never allowed. The mass assignment defense as a
// theorem, for every field name at once (isManager, payGrade, ...).
@id("guardrail-mass-assignment-fail-closed")
forbid(
  principal,
  action == Action::"UpdateEmployeeField",
  resource
) when {
  !(context has field && Contract::"Employee/writers".hasTag(context.field))
};
