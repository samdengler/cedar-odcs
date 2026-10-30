// Guardrail: while acting for a party, a write is made only for that
// party. The request leg never has the order, so the party is the
// customer the call names. A refund is the employee's own act and is
// never made while acting, so it is not listed.
@id("guardrail-acting-writes-bounded-by-customer")
forbid(
  principal,
  action in [
    Action::"UpdateOrder",
    Action::"CancelOrder",
    Action::"UpdateOrderField"
  ],
  resource
) when {
  context has actingFor &&
  !(context has input && context.input has customerId &&
    context.input.customerId == context.actingFor)
};
