// Guardrail: while a pair is presented, specialist paths are never
// written, whoever the specialist is.
@id("guardrail-specialist-paths-off-with-pair")
forbid(
  principal,
  action == Action::"UpdateReservationField",
  resource
) when {
  context has presented &&
  context has field &&
  Contract::"Reservation/writers".hasTag(context.field) &&
  Contract::"Reservation/writers".getTag(context.field) == "specialist"
};
