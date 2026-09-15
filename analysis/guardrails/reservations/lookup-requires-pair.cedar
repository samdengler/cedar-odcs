// Guardrail: a lookup is never attempted without a presented pair.
// A locator alone is not possession.
@id("guardrail-lookup-requires-pair")
forbid(
  principal,
  action == Action::"LookupReservation",
  resource
) when {
  !(context has presented)
};
