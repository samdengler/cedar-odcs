// Guardrail: possession reads public and confidential leaves only.
// Internal leaves, the specialist's remarks, are never revealed to a
// caller whose only credential is the pair.
@id("guardrail-possession-reads-customer-levels-only")
forbid(
  principal,
  action == Action::"ReadReservationField",
  resource
) when {
  context has presented &&
  context has field &&
  Contract::"Reservation".hasTag(context.field) &&
  !(["public", "confidential"].contains(Contract::"Reservation".getTag(context.field)))
};
