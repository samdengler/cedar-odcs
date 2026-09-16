// Guardrail: support reaches a confidential field only through
// ownership of the order, never through the support role itself.
@id("guardrail-support-confidential-only-as-owner")
forbid(
  principal in Role::"support",
  action == Action::"ReadOrderField",
  resource
) when {
  !(resource has owner && resource.owner == principal) &&
  context has field &&
  Contract::"Order".hasTag(context.field) &&
  Contract::"Order".getTag(context.field) == "confidential"
};
