// BOLA on writes: iteration 1's two read policies, carried forward
// unchanged, plus one write policy.
//
// The rule is the same ownership relationship. What changes is the
// placement: reads can be enforced on the response leg, but a write
// must be gated on the request leg, before the upstream API applies
// anything. Support has no write permit: reading any order and
// updating none are different functions, which is where API5 begins.
//
// New policies are appended, never inserted: cedarpy reports
// determining policies by position (policy0, policy1, ...), and the
// test corpus refers to those ids.

// P1 (policy0): A customer may read an order they own.
@id("customer-reads-own-order")
permit(
  principal,
  action == Action::"ReadOrder",
  resource
) when {
  resource.owner == principal
};

// P2 (policy1): A support agent may read any order.
@id("support-reads-any-order")
permit(
  principal in Role::"support",
  action == Action::"ReadOrder",
  resource
);

// P3 (policy2): A customer may update an order they own. Mirrors P1,
// including its error behavior on a guessed order id, which the
// corpus pins.
@id("customer-updates-own-order")
permit(
  principal,
  action == Action::"UpdateOrder",
  resource
) when {
  resource.owner == principal
};
