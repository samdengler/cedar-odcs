// Guardrail: while acting for a party, only public and confidential
// fields are readable, the customer's own levels. Internal fields,
// which support reads in direct mode, are never revealed through the
// acting mode, whatever the tag map holds.
@id("guardrail-acting-reads-customer-levels-only")
forbid(
  principal,
  action == Action::"ReadOrderField",
  resource
) when {
  context has actingFor &&
  context has field &&
  Contract::"Order".hasTag(context.field) &&
  !(["public", "confidential"].contains(Contract::"Order".getTag(context.field)))
};
