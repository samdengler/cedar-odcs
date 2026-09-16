// Guardrail, revised for the specialist's view: a lookup is attempted
// only with a presented pair or by a specialist, the acted-for human
// or the principal.
@id("guardrail-lookup-requires-pair-or-specialist")
forbid(
  principal,
  action == Action::"LookupReservation",
  resource
) when {
  !(context has presented) &&
  !((context has actingFor && context.actingFor in Role::"specialist") ||
    (!(context has actingFor) && principal in Role::"specialist"))
};
