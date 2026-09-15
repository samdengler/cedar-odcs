// Guardrail: listing has no customer form. Only a specialist without
// a pair in hand lists.
@id("guardrail-list-requires-specialist")
forbid(
  principal,
  action == Action::"ListReservations",
  resource
) when {
  context has presented ||
  !((context has actingFor && context.actingFor in Role::"specialist") ||
    (!(context has actingFor) && principal in Role::"specialist"))
};
