// Guardrail, revised for the specialist's view: nothing of a record is
// readable without a presented pair except by a specialist.
@id("guardrail-read-requires-pair-or-specialist")
forbid(
  principal,
  action in [Action::"ReadReservation", Action::"ReadReservationField"],
  resource
) when {
  !(context has presented) &&
  !((context has actingFor && context.actingFor in Role::"specialist") ||
    (!(context has actingFor) && principal in Role::"specialist"))
};
