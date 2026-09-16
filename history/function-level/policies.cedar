// Function level (API5): the six policies from iterations 1 through 4,
// carried forward unchanged, plus five verb and role policies appended
// at the end of this file.
//
// From iteration 4, mass assignment (API3 writes): the five policies
// from iterations 1 through 3, plus one write-field policy.
//
// Writability is its own dimension, separate from read sensitivity:
// status is public to read and writable by nobody through this path,
// while shippingAddress is confidential to read and exactly the thing
// an owner should update. So writes get their own map, entity tags on
// Contract::"Order/writers": each tag key is a field name, each tag
// value names the writer, "owner" or "system". A field missing from
// the map fails the hasTag guard, so an undeclared field in a write
// payload fails closed: the mass assignment defense.
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

// P3 (policy2): A customer may update an order they own.
@id("customer-updates-own-order")
permit(
  principal,
  action == Action::"UpdateOrder",
  resource
) when {
  resource.owner == principal
};

// P4 (policy3): A customer may read public and confidential fields of
// an order they own.
@id("customer-fields-on-own-order")
permit(
  principal,
  action == Action::"ReadOrderField",
  resource
) when {
  resource has owner &&
  resource.owner == principal &&
  context has field &&
  Contract::"Order".hasTag(context.field) &&
  ["public", "confidential"].contains(Contract::"Order".getTag(context.field))
};

// P5 (policy4): A support agent may read public and internal fields
// of any order.
@id("support-fields-on-any-order")
permit(
  principal in Role::"support",
  action == Action::"ReadOrderField",
  resource
) when {
  context has field &&
  Contract::"Order".hasTag(context.field) &&
  ["public", "internal"].contains(Contract::"Order".getTag(context.field))
};

// P6 (policy5): A customer may update owner-writable fields of an
// order they own. There is no support policy for writes: the role
// grants no field writes, matching the object-level gate.
@id("customer-updates-own-order-fields")
permit(
  principal,
  action == Action::"UpdateOrderField",
  resource
) when {
  resource has owner &&
  resource.owner == principal &&
  context has field &&
  Contract::"Order/writers".hasTag(context.field) &&
  Contract::"Order/writers".getTag(context.field) == "owner"
};

// Iteration 5, function level (API5): roles hold verbs. Two new verbs
// and the first role-granted write path. CancelOrder is held by the
// owner and by support; RefundOrder is held by finance alone. Support
// gains UpdateOrder at object level, and through the writers map may
// set exactly the fields whose writer is "support". Ownership grants
// no refund, and a role that holds refund does not thereby hold read.
//
// New object-level policies guard the owner access with `has`, the
// lesson the analysis reveal taught: an order the store does not know
// then fails closed instead of raising an evaluation error.

// P7 (policy6): A customer may cancel an order they own.
@id("customer-cancels-own-order")
permit(
  principal,
  action == Action::"CancelOrder",
  resource
) when {
  resource has owner &&
  resource.owner == principal
};

// P8 (policy7): A support agent may cancel any order.
@id("support-cancels-any-order")
permit(
  principal in Role::"support",
  action == Action::"CancelOrder",
  resource
);

// P9 (policy8): Finance may refund any order. No other principal
// holds the verb: not the owner, not support.
@id("finance-refunds-any-order")
permit(
  principal in Role::"finance",
  action == Action::"RefundOrder",
  resource
);

// P10 (policy9): A support agent may update any order at object
// level. This revises iteration 2's decision that the role grants no
// updates; the fields the role may set are bounded by P11.
@id("support-updates-any-order")
permit(
  principal in Role::"support",
  action == Action::"UpdateOrder",
  resource
);

// P11 (policy10): A support agent may set the fields whose writer is
// "support", on any order.
@id("support-updates-support-fields")
permit(
  principal in Role::"support",
  action == Action::"UpdateOrderField",
  resource
) when {
  context has field &&
  Contract::"Order/writers".hasTag(context.field) &&
  Contract::"Order/writers".getTag(context.field) == "support"
};
