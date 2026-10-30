// Guardrail: an agent with no one to act for reads no record, lists
// nothing, and changes nothing. The assistant holds the grants of the
// person it talks with and none of its own. A lookup is permitted to
// anyone and decided on the response, so it is left out.
@id("guardrail-the-assistant-alone-is-granted-nothing")
forbid(
  principal,
  action in [
    Action::"ReadEmployee",
    Action::"ReadEmployeeField",
    Action::"UpdateEmployee",
    Action::"UpdateEmployeeField",
    Action::"ListEmployees"
  ],
  resource
) when {
  principal is Agent &&
  !(context has actingFor)
};
