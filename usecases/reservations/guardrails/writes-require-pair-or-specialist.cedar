// Guardrail, revised for the specialist's view: no write without a
// presented pair except by a specialist.
@id("guardrail-writes-require-pair-or-specialist")
forbid(
  principal,
  action in [Action::"UpdateReservation", Action::"UpdateReservationField", Action::"CancelReservation"],
  resource
) when {
  !(context has presented) &&
  !((context has actingFor && context.actingFor in Role::"specialist") ||
    (!(context has actingFor) && principal in Role::"specialist"))
};
