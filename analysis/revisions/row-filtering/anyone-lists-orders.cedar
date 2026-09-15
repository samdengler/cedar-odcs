// Declared revision: iteration 9's one permit, on the list verb the
// shared generated schema declares. The text is P13 of
// row-filtering/policies.cedar.
@id("anyone-lists-orders")
permit(
  principal,
  action == Action::"ListOrders",
  resource == Collection::"orders"
);
