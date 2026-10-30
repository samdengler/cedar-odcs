// Guardrail: a field whose writer is "system" is writable by nobody
// through this tool, whoever asks: the employee id, the work email,
// the salary, and the bank account pay goes to. A request to change
// the address and the salary together is refused whole.
@id("guardrail-system-fields-unwritable")
forbid(
  principal,
  action == Action::"UpdateEmployeeField",
  resource
) when {
  context has field &&
  Contract::"Employee/writers".hasTag(context.field) &&
  Contract::"Employee/writers".getTag(context.field) == "system"
};
