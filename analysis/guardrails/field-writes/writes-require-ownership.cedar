// Guardrail: no field of an order is writable by anyone but its
// owner. Stronger than the read side, where the support role reaches
// public and internal fields of any order: on the write side there is
// no role-granted path at all.
@id("guardrail-writes-require-ownership")
forbid(
  principal,
  action == Action::"UpdateOrderField",
  resource
) when {
  !(resource has owner && resource.owner == principal)
};
