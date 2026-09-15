// Guardrail: through the support role, a field is writable only when
// the writers map names "support" as its writer. Replaces iteration
// 4's writes-require-ownership, which this iteration retires knowingly
// by granting the role an object-level update: the role-granted write
// path now exists, and this forbid bounds it. An agent who personally
// owns the order still writes as the owner.
@id("guardrail-role-writes-only-role-fields")
forbid(
  principal in Role::"support",
  action == Action::"UpdateOrderField",
  resource
) when {
  !(resource has owner && resource.owner == principal) &&
  !(context has field &&
    Contract::"Order/writers".hasTag(context.field) &&
    Contract::"Order/writers".getTag(context.field) == "support")
};
