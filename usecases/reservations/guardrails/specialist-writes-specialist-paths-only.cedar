// Guardrail: without a pair, a specialist writes only paths whose
// writer is "specialist". The customer's paths need possession, even
// for a specialist.
@id("guardrail-specialist-writes-specialist-paths-only")
forbid(
  principal,
  action == Action::"UpdateReservationField",
  resource
) when {
  !(context has presented) &&
  !(context has field &&
    Contract::"Reservation/writers".hasTag(context.field) &&
    Contract::"Reservation/writers".getTag(context.field) == "specialist")
};
