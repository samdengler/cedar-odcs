// Guardrail: a presented pair reaches only the record it names. The
// locator must be the record's and the last name must be the holder's;
// a pair valid for one reservation reads nothing of another, and a
// co-traveler's last name reads nothing.
@id("guardrail-possession-names-the-record")
forbid(
  principal,
  action in [Action::"ReadReservation", Action::"ReadReservationField"],
  resource
) when {
  context has presented &&
  !(resource has recordLocator &&
    resource has holderLastName &&
    resource.recordLocator == context.presented.locator &&
    resource.holderLastName == context.presented.lastName)
};
