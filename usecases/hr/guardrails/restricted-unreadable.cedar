// Guardrail: no reader holds the restricted level, so a field
// classified restricted, the bank account pay goes to, is never
// allowed, whatever the tag map holds and whoever asks: the employee,
// a colleague, or HR.
@id("guardrail-restricted-unreadable")
forbid(
  principal,
  action == Action::"ReadEmployeeField",
  resource
) when {
  context has field &&
  Contract::"Employee".hasTag(context.field) &&
  Contract::"Employee".getTag(context.field) == "restricted"
};
