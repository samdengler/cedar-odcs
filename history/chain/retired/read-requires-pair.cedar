// Guardrail: nothing of a record is readable without a presented
// pair. True while possession is the only path; the specialist view
// of iteration 13 will retire it knowingly.
@id("guardrail-read-requires-pair")
forbid(
  principal,
  action in [Action::"ReadReservation", Action::"ReadReservationField"],
  resource
) when {
  !(context has presented)
};
