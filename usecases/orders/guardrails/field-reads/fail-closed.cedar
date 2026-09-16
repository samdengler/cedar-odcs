// Guardrail: a field request with no field named, or naming a field
// missing from the contract's tag map, is never allowed. This is the
// fail-closed invariant as a theorem, for every field name at once.
//
// The condition is the De Morgan form of "not (field present and
// declared)": Cedar's strict typechecker tracks the `has` guard
// through &&, so `context.field` inside the parentheses is guarded;
// the equivalent `!(has) || !hasTag` form is rejected as unguarded.
@id("guardrail-fail-closed")
forbid(
  principal,
  action == Action::"ReadOrderField",
  resource
) when {
  !(context has field && Contract::"Order".hasTag(context.field))
};
