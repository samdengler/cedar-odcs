// Row filtering (iteration 9): iteration 6's twelve policies, carried
// unchanged through iteration 7, plus one list verb appended at the
// end of this file.
//
// On behalf of access (iteration 6): the eleven policies from
// iterations 1 through 5, each revised for mode, and no new permits.
//
// Three modes exist. A customer interacting directly, an employee
// interacting directly, and an employee acting for a customer. The
// principal is always the actor, the party whose credential made the
// call. In on behalf of mode the context carries the acted-for party
// as `actingFor`; in direct mode the attribute is absent.
//
// Two rules give every policy its mode. Ownership policies compare the
// owner to the acted-for party when present and to the principal
// otherwise, so an employee acting for alice holds alice's ownership.
// Role policies require direct mode, so the employee's own grants are
// off while acting for someone: the caller holds the customer's
// access, no more.
//
// Every carried corpus case is direct mode and still passes: the
// revision changes no direct-mode decision, which the composition
// proofs in analysis/ state as a theorem.
//
// Policy ids stay positional (policy0, policy1, ...); the corpora
// refer to them.

// P1 (policy0): A customer may read an order they own; an employee
// acting for the customer holds the same.
@id("customer-reads-own-order")
permit(
  principal,
  action == Action::"ReadOrder",
  resource
) when {
  resource.owner == (if context has actingFor then context.actingFor else principal)
};

// P2 (policy1): A support agent may read any order, in direct mode.
@id("support-reads-any-order")
permit(
  principal in Role::"support",
  action == Action::"ReadOrder",
  resource
) when {
  !(context has actingFor)
};

// P3 (policy2): A customer may update an order they own; an employee
// acting for the customer holds the same.
@id("customer-updates-own-order")
permit(
  principal,
  action == Action::"UpdateOrder",
  resource
) when {
  resource.owner == (if context has actingFor then context.actingFor else principal)
};

// P4 (policy3): A customer may read public and confidential fields of
// an order they own; an employee acting for the customer holds the
// same.
@id("customer-fields-on-own-order")
permit(
  principal,
  action == Action::"ReadOrderField",
  resource
) when {
  resource has owner &&
  resource.owner == (if context has actingFor then context.actingFor else principal) &&
  context has field &&
  Contract::"Order".hasTag(context.field) &&
  ["public", "confidential"].contains(Contract::"Order".getTag(context.field))
};

// P5 (policy4): A support agent may read public and internal fields
// of any order, in direct mode.
@id("support-fields-on-any-order")
permit(
  principal in Role::"support",
  action == Action::"ReadOrderField",
  resource
) when {
  !(context has actingFor) &&
  context has field &&
  Contract::"Order".hasTag(context.field) &&
  ["public", "internal"].contains(Contract::"Order".getTag(context.field))
};

// P6 (policy5): A customer may update owner-writable fields of an
// order they own; an employee acting for the customer holds the same.
@id("customer-updates-own-order-fields")
permit(
  principal,
  action == Action::"UpdateOrderField",
  resource
) when {
  resource has owner &&
  resource.owner == (if context has actingFor then context.actingFor else principal) &&
  context has field &&
  Contract::"Order/writers".hasTag(context.field) &&
  Contract::"Order/writers".getTag(context.field) == "owner"
};

// P7 (policy6): A customer may cancel an order they own; an employee
// acting for the customer holds the same.
@id("customer-cancels-own-order")
permit(
  principal,
  action == Action::"CancelOrder",
  resource
) when {
  resource has owner &&
  resource.owner == (if context has actingFor then context.actingFor else principal)
};

// P8 (policy7): A support agent may cancel any order, in direct mode.
@id("support-cancels-any-order")
permit(
  principal in Role::"support",
  action == Action::"CancelOrder",
  resource
) when {
  !(context has actingFor)
};

// P9 (policy8): Finance may refund any order, in direct mode. A refund
// is the employee's own act; acting for a customer does not carry it.
@id("finance-refunds-any-order")
permit(
  principal in Role::"finance",
  action == Action::"RefundOrder",
  resource
) when {
  !(context has actingFor)
};

// P10 (policy9): A support agent may update any order at object
// level, in direct mode.
@id("support-updates-any-order")
permit(
  principal in Role::"support",
  action == Action::"UpdateOrder",
  resource
) when {
  !(context has actingFor)
};

// P11 (policy10): A support agent may set the fields whose writer is
// "support", on any order, in direct mode.
@id("support-updates-support-fields")
permit(
  principal in Role::"support",
  action == Action::"UpdateOrderField",
  resource
) when {
  !(context has actingFor) &&
  context has field &&
  Contract::"Order/writers".hasTag(context.field) &&
  Contract::"Order/writers".getTag(context.field) == "support"
};

// G1 (policy11): Only an employee may act for another party. A
// customer token carrying an actor claim, or an unknown principal
// claiming to act for a customer, matches this forbid and nothing
// else matters.
@id("only-employees-act-for-others")
forbid(
  principal,
  action,
  resource
) when {
  context has actingFor &&
  !(principal in Role::"employee")
};

// Iteration 9, row filtering: one new verb for list endpoints. The
// list itself decides nothing. Every principal may call it, in either
// mode, because the rows are authorized one by one on the response
// leg with ReadOrder, the same question iteration 1 asked of a single
// order. The only-employees-act-for-others forbid still applies.

// P13 (policy12): Anyone may list orders; the rows decide.
@id("anyone-lists-orders")
permit(
  principal,
  action == Action::"ListOrders",
  resource == Collection::"orders"
);
