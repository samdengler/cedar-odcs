// Guardrail: an internal field, HR's notes, is read only when an HR
// partner is the person on the call, directly or through the
// assistant. The employee does not read the notes on their own record,
// their manager does not, and HR acting for an employee does not.
@id("guardrail-internal-only-to-hr")
forbid(
  principal,
  action == Action::"ReadEmployeeField",
  resource
) when {
  !((context has actingFor && context.actingFor in Role::"hr") ||
    (!(context has actingFor) && principal in Role::"hr")) &&
  context has field &&
  Contract::"Employee".hasTag(context.field) &&
  Contract::"Employee".getTag(context.field) == "internal"
};
