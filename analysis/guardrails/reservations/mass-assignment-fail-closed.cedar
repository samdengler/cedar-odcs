// Guardrail: a write naming no path, or a path absent from the
// writers map, is never allowed, nested paths included.
@id("guardrail-mass-assignment-fail-closed")
forbid(
  principal,
  action == Action::"UpdateReservationField",
  resource
) when {
  !(context has field && Contract::"Reservation/writers".hasTag(context.field))
};
