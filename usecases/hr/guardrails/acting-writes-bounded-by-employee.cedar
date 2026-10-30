// Guardrail: while acting for someone, as HR for an employee or as the
// assistant for whoever it talks with, a write is made only for the
// person acted for. The request leg never has the record, so the
// person is the one the call names, which is also the record it
// writes.
@id("guardrail-acting-writes-bounded-by-employee")
forbid(
  principal,
  action in [
    Action::"UpdateEmployee",
    Action::"UpdateEmployeeField"
  ],
  resource
) when {
  context has actingFor &&
  !(context has input && context.input has employeeId &&
    context.input.employeeId == context.actingFor)
};
