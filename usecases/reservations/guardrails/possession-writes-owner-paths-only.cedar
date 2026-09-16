// Guardrail: possession writes only paths whose writer is "owner".
// The passenger list, the fare, the payment, and the remarks are
// never written through the pair, whatever the writers map holds for
// them short of "owner".
@id("guardrail-possession-writes-owner-paths-only")
forbid(
  principal,
  action == Action::"UpdateReservationField",
  resource
) when {
  context has presented &&
  !(context has field &&
    Contract::"Reservation/writers".hasTag(context.field) &&
    Contract::"Reservation/writers".getTag(context.field) == "owner")
};
