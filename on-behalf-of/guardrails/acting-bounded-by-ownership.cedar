// Guardrail: while acting for a party, nothing is allowed outside
// that party's ownership. For every verb at once: the actor's own
// roles grant nothing in on behalf of mode, so the mode holds exactly
// the acted-for customer's access.
@id("guardrail-acting-bounded-by-ownership")
forbid(
  principal,
  action,
  resource
) when {
  context has actingFor &&
  !(resource has owner && resource.owner == context.actingFor)
};
