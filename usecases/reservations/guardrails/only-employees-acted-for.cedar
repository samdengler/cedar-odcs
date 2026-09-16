// Guardrail: an acted-for human outside the employee role is granted
// nothing, on any verb. Restates the policy set's own forbid as a
// theorem over every action, the list included.
@id("guardrail-only-employees-acted-for")
forbid(
  principal,
  action,
  resource
) when {
  context has actingFor &&
  !(context.actingFor in Role::"employee")
};
