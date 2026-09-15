// Guardrail: a restricted leaf, passport numbers and medical requests
// among them, is readable by nobody through this path.
@id("guardrail-restricted-unreadable")
forbid(
  principal,
  action == Action::"ReadReservationField",
  resource
) when {
  context has field &&
  Contract::"Reservation".hasTag(context.field) &&
  Contract::"Reservation".getTag(context.field) == "restricted"
};
