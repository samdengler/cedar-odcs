// Guardrail: while acting for someone, only the fields whose writer is
// "owner" are writable. HR changes an employee's address for them and
// changes no title, department, or note while doing so; the assistant
// changes no title, department, or note even for an HR partner.
@id("guardrail-acting-writes-owner-fields-only")
forbid(
  principal,
  action == Action::"UpdateEmployeeField",
  resource
) when {
  context has actingFor &&
  context has field &&
  Contract::"Employee/writers".hasTag(context.field) &&
  Contract::"Employee/writers".getTag(context.field) != "owner"
};
