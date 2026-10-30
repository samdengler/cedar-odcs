// Guardrail: a confidential field, a home address, a personal phone,
// a salary, is read only from the record of the person on the call,
// by that record's manager, or by HR. A colleague reading the
// directory never sees one.
@id("guardrail-confidential-only-to-the-employee-their-manager-and-hr")
forbid(
  principal,
  action == Action::"ReadEmployeeField",
  resource
) when {
  !(resource has employeeId &&
    ((context has actingFor && resource.employeeId == context.actingFor) ||
     (!(context has actingFor) && resource.employeeId == principal))) &&
  !(resource has manager &&
    ((context has actingFor && resource.manager == context.actingFor) ||
     (!(context has actingFor) && resource.manager == principal))) &&
  !((context has actingFor && context.actingFor in Role::"hr") ||
    (!(context has actingFor) && principal in Role::"hr")) &&
  context has field &&
  Contract::"Employee".hasTag(context.field) &&
  Contract::"Employee".getTag(context.field) == "confidential"
};
