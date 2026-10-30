// Guardrail: a field whose writer is "owner", the home address and
// the personal phone, is set only on the record of the person on the
// call: the caller's own, or that of the employee HR or the assistant
// acts for. HR in direct mode never sets one, and no employee sets a
// colleague's.
@id("guardrail-owner-fields-only-on-own-record")
forbid(
  principal,
  action == Action::"UpdateEmployeeField",
  resource
) when {
  !(context has input && context.input has employeeId &&
    ((context has actingFor && context.input.employeeId == context.actingFor) ||
     (!(context has actingFor) && context.input.employeeId == principal))) &&
  context has field &&
  Contract::"Employee/writers".hasTag(context.field) &&
  Contract::"Employee/writers".getTag(context.field) == "owner"
};
