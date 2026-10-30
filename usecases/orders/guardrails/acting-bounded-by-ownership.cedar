// Guardrail, revised for the list verb and for writes on the request:
// while acting for a party, nothing is read from an order outside that
// party's ownership. The reads are decided on the order the API
// returned, so ownership is its owner; the writes are in
// acting-writes-bounded-by-customer.cedar. The list and lookup calls
// are named out, because they are the verbs with no order in hand:
// they decide nothing, and every order they return is authorized by
// ReadOrder, which this guardrail still covers.
@id("guardrail-acting-bounded-by-ownership")
forbid(
  principal,
  action in [
    Action::"ReadOrder",
    Action::"ReadOrderField"
  ],
  resource
) when {
  context has actingFor &&
  !(resource has owner && resource.owner == context.actingFor)
};
