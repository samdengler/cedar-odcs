// Guardrail: a field request naming no path, or a path the contract
// does not declare, is never allowed. Paths include nested ones such
// as passengers[].seat; the map is keyed by path.
@id("guardrail-fail-closed")
forbid(
  principal,
  action == Action::"ReadReservationField",
  resource
) when {
  !(context has field && Contract::"Reservation".hasTag(context.field))
};
