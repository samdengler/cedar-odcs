// BOLA MVP: two policies, default deny.
//
// Cedar denies everything unless a permit policy matches.
// That default-deny is itself the core BOLA defense: an object
// you have no stated relationship to is unreachable.

// P1: A customer may read an order they own.
@id("customer-reads-own-order")
permit(
  principal,
  action == Action::"ReadOrder",
  resource
) when {
  resource.owner == principal
};

// P2: A support agent may read any order.
@id("support-reads-any-order")
permit(
  principal in Role::"support",
  action == Action::"ReadOrder",
  resource
);
