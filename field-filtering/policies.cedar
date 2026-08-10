// Field filtering (API3): iteration 1's two object-level policies,
// carried forward unchanged, plus two field-level policies.
//
// The field policies never name fields. The classification map lives
// in entities.json as entity tags on Contract::"Order": each tag key
// is a field name, each tag value is the field's classification
// level, one of public, internal, confidential, restricted. The
// contract classifies; policies grant levels to readers. No policy
// grants restricted yet, so those fields are readable by nobody, and
// a field missing from the map fails the hasTag guard, so undeclared
// fields fail closed.
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

// P3 (policy2): A customer may read public and confidential fields of
// an order they own. The has and hasTag guards make unknown orders
// and undeclared fields fail cleanly instead of erroring.
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

// P4 (policy3): A support agent may read public and internal fields
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
