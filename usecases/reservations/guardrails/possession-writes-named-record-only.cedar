// Guardrail: a presented pair writes only the record it names, for
// every write verb at once.
@id("guardrail-possession-writes-named-record-only")
forbid(
  principal,
  action in [Action::"UpdateReservation", Action::"UpdateReservationField", Action::"CancelReservation"],
  resource
) when {
  context has presented &&
  !(resource has recordLocator &&
    resource has holderLastName &&
    resource.recordLocator == context.presented.locator &&
    resource.holderLastName == context.presented.lastName)
};
