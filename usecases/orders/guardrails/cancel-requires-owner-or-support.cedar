// Guardrail, revised for mode and for writes on the request: an order
// is cancelled for the customer the call names when that is the
// caller, or the party an employee acts for, or by support in direct
// mode.
@id("guardrail-cancel-requires-owner-or-support")
forbid(
  principal,
  action == Action::"CancelOrder",
  resource
) when {
  !(context has input && context.input has customerId &&
    context.input.customerId == (if context has actingFor then context.actingFor else principal)) &&
  !(!(context has actingFor) && principal in Role::"support")
};
