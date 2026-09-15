// Reservations, iteration 11: access by possession of a record
// locator and the holder's last name.
//
// There is no customer identity. Whoever presents the pair holds the
// reservation, so the customer is never a principal: the pair travels
// in context as `presented`, from the tool input, and is checked
// against the record. The record's locator and holder last name are
// attributes of the resource entity, built from the payload on the
// response leg, so the check runs there. On the request leg nothing
// can be verified, and the lookup is permitted whenever a pair is
// presented; the response leg decides what, if anything, comes back.
//
// Policy ids are positional (policy0, policy1, ...); the corpus refers
// to them.

// P1 (policy0): A lookup may be attempted by anyone presenting a
// pair. This is the request leg's whole decision.
@id("lookup-with-presented-pair")
permit(
  principal,
  action == Action::"LookupReservation",
  resource
) when {
  context has presented
};

// P2 (policy1): The record is readable when its locator and holder
// last name are the presented ones.
@id("read-by-possession")
permit(
  principal,
  action == Action::"ReadReservation",
  resource
) when {
  context has presented &&
  resource has recordLocator &&
  resource has holderLastName &&
  resource.recordLocator == context.presented.locator &&
  resource.holderLastName == context.presented.lastName
};

// P3 (policy2): Public and confidential leaves of a possessed record
// are readable, looked up by path in the classification map.
@id("fields-by-possession")
permit(
  principal,
  action == Action::"ReadReservationField",
  resource
) when {
  context has presented &&
  resource has recordLocator &&
  resource has holderLastName &&
  resource.recordLocator == context.presented.locator &&
  resource.holderLastName == context.presented.lastName &&
  context has field &&
  Contract::"Reservation".hasTag(context.field) &&
  ["public", "confidential"].contains(Contract::"Reservation".getTag(context.field))
};
