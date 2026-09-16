// Restriction: added to both sides of a comparison, this forbid
// removes every on behalf of request, so the equivalence is proven
// over direct mode alone. Iteration 6 promised that no direct-mode
// decision changed; this is the region where the promise applies.
@id("restriction-direct-mode")
forbid(
  principal,
  action,
  resource
) when {
  context has actingFor
};
