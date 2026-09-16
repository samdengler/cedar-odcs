// Guardrail: nobody outside the finance role ever refunds an order.
// Ownership grants no refund, and neither does the support role: the
// function level invariant (API5) as a theorem.
@id("guardrail-refund-requires-finance")
forbid(
  principal,
  action == Action::"RefundOrder",
  resource
) when {
  !(principal in Role::"finance")
};
