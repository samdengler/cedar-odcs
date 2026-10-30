// Guardrail: a token in which anyone but HR or the HR assistant acts
// for an employee is granted nothing, on every verb.
@id("guardrail-only-hr-and-the-assistant-act-for-employees")
forbid(
  principal,
  action,
  resource
) when {
  context has actingFor &&
  !(principal in Role::"hr") &&
  !(principal == Agent::"hr-assistant")
};
