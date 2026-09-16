// Guardrail: no reader holds the restricted level, so a field
// classified restricted is never allowed, whatever the tag map holds
// and whoever asks.
@id("guardrail-restricted-unreadable")
forbid(
  principal,
  action == Action::"ReadOrderField",
  resource
) when {
  context has field &&
  Contract::"Order".hasTag(context.field) &&
  Contract::"Order".getTag(context.field) == "restricted"
};
