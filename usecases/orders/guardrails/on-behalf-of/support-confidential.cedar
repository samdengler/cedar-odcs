// Guardrail, revised for mode: support reaches a confidential field
// only through ownership of the order, its own or that of the party
// it acts for; never through the support role itself.
@id("guardrail-support-confidential-only-as-owner")
forbid(
  principal in Role::"support",
  action == Action::"ReadOrderField",
  resource
) when {
  !(resource has owner &&
    resource.owner == (if context has actingFor then context.actingFor else principal)) &&
  context has field &&
  Contract::"Order".hasTag(context.field) &&
  Contract::"Order".getTag(context.field) == "confidential"
};
