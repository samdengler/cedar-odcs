// Guardrail: no write reaches a reservation without a presented pair,
// whoever asks. The specialist's own writes are iteration 13's, and
// will revise this knowingly.
@id("guardrail-writes-require-pair")
forbid(
  principal,
  action in [Action::"UpdateReservation", Action::"UpdateReservationField", Action::"CancelReservation"],
  resource
) when {
  !(context has presented)
};
