// Restriction: added to both sides of a comparison, this forbid
// removes the three verbs a customer writes with, so the equivalence
// is proven over every other verb. The orders use case moved those
// writes from the order's owner, which the request leg never has, to
// the customer the call names (context.input.customerId); the corpus
// and the guardrails pin the new decisions. Every read, the refund,
// and the list are proven to decide as iteration 9 did.
@id("restriction-reads-and-refunds")
forbid(
  principal,
  action in [
    Action::"UpdateOrder",
    Action::"CancelOrder",
    Action::"UpdateOrderField"
  ],
  resource
);
