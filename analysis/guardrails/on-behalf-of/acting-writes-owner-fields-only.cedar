// Guardrail: while acting for a party, only owner-writable fields are
// writable. Support's own field, internalNotes, is off while acting.
@id("guardrail-acting-writes-owner-fields-only")
forbid(
  principal,
  action == Action::"UpdateOrderField",
  resource
) when {
  context has actingFor &&
  context has field &&
  Contract::"Order/writers".hasTag(context.field) &&
  Contract::"Order/writers".getTag(context.field) != "owner"
};
