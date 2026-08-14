// Guardrail: a field whose writer is "system" is writable by nobody
// through this path, whoever asks, including the order's owner.
@id("guardrail-system-fields-unwritable")
forbid(
  principal,
  action == Action::"UpdateOrderField",
  resource
) when {
  context has field &&
  Contract::"Order/writers".hasTag(context.field) &&
  Contract::"Order/writers".getTag(context.field) == "system"
};
