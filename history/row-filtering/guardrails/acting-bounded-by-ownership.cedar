// Guardrail, revised for the list verb: while acting for a party,
// nothing is allowed on an order outside that party's ownership. The
// list call is named out, because it is the one verb with no order
// to own: listing decides nothing, and every row it returns is
// authorized by ReadOrder, which this guardrail still covers.
@id("guardrail-acting-bounded-by-ownership")
forbid(
  principal,
  action in [
    Action::"ReadOrder",
    Action::"UpdateOrder",
    Action::"CancelOrder",
    Action::"RefundOrder",
    Action::"ReadOrderField",
    Action::"UpdateOrderField"
  ],
  resource
) when {
  context has actingFor &&
  !(resource has owner && resource.owner == context.actingFor)
};
