// Guardrail: a presented pair writes only the record it names, for
// every write verb at once.
//
// Retired: it held only on a record the request leg fetched first,
// and in deployment that fetch read test fixtures. The request leg
// never has the reservation; a write by possession is decided on the
// presented pair, and the Reservations API refuses a pair that names
// no reservation.
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
