// Guardrail: a confidential field the employee sets about themself,
// the home address and the personal phone, is read only from the
// record of the person on the call, or by HR. A manager reads a
// report's pay and never where the report lives.
@id("guardrail-personal-fields-only-to-the-employee-and-hr")
forbid(
  principal,
  action == Action::"ReadEmployeeField",
  resource
) when {
  !(resource has employeeId &&
    ((context has actingFor && resource.employeeId == context.actingFor) ||
     (!(context has actingFor) && resource.employeeId == principal))) &&
  !((context has actingFor && context.actingFor in Role::"hr") ||
    (!(context has actingFor) && principal in Role::"hr")) &&
  context has field &&
  Contract::"Employee".hasTag(context.field) &&
  Contract::"Employee".getTag(context.field) == "confidential" &&
  Contract::"Employee/writers".hasTag(context.field) &&
  Contract::"Employee/writers".getTag(context.field) == "owner"
};
