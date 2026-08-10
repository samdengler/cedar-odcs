// Field filtering (API3): iteration 1's two object-level policies,
// carried forward unchanged, plus two field-level policies.
//
// The field policies never name fields. They ask whether the field in
// the request context belongs to a classification class, and the
// class memberships live in entities.json with the rest of the facts.
// A field in no class is readable by nobody: default deny does the
// rest, so undeclared fields fail closed.
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

// P3 (policy2): A customer may read customer-visible fields of an
// order they own. The `has` guards make unknown orders and requests
// without a field fail cleanly instead of erroring.
@id("customer-fields-on-own-order")
permit(
  principal,
  action == Action::"ReadOrderField",
  resource
) when {
  resource has owner &&
  resource.owner == principal &&
  context has field &&
  context.field in FieldClass::"customer-visible"
};

// P4 (policy3): A support agent may read operational fields of any
// order.
@id("support-operational-fields")
permit(
  principal in Role::"support",
  action == Action::"ReadOrderField",
  resource
) when {
  context has field &&
  context.field in FieldClass::"operational"
};
