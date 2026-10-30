// Reservations, iterations 11 through 13: access by possession of a
// record locator and the holder's last name; reads, then writes,
// then the specialist's view.
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

// Iteration 12: writes by possession. Anyone who knows the locator
// and the holder's last name may change the contact details, a seat,
// or cancel the reservation, as the airline allows on the web. A
// write is decided before the API is called, and the request leg
// never has the record, so the policies below require the pair and
// bound the paths; whether the pair names a reservation is the
// Reservations API's to decide, and it refuses a write whose pair
// does not. The locator is the tool's id argument, so the pair
// always names the record the call writes (engine/calls.py).

// P4 (policy3): The record may be updated by possession: the call
// presents the pair.
@id("update-by-possession")
permit(
  principal,
  action == Action::"UpdateReservation",
  resource
) when {
  context has presented
};

// P5 (policy4): Possession writes the paths whose writer is "owner":
// the contact details and a passenger's seat. The passenger list,
// the fare, the payment, and the specialist's remarks stay closed.
@id("update-fields-by-possession")
permit(
  principal,
  action == Action::"UpdateReservationField",
  resource
) when {
  context has presented &&
  context has field &&
  Contract::"Reservation/writers".hasTag(context.field) &&
  Contract::"Reservation/writers".getTag(context.field) == "owner"
};

// P6 (policy5): The reservation may be cancelled by possession.
@id("cancel-by-possession")
permit(
  principal,
  action == Action::"CancelReservation",
  resource
) when {
  context has presented
};

// Iteration 13: the specialist's view, and the agent as a party.
//
// Three parties can be on a call. The principal is whoever holds the
// token: the agent, typed Agent, in a customer conversation or when a
// specialist works through it; a User when a specialist calls
// without the agent. The human a token was exchanged for is
// context.actingFor. The customer is only ever the presented pair.
//
// "The specialist" in the policies below is therefore the acted-for
// human when there is one, else the principal. The specialist's own
// view is on only when no pair is presented: a specialist presenting
// a pair works in the customer's view, by the possession policies
// above, and sees and writes what the customer would.

// P7 (policy6): A specialist may look up any reservation, without a
// pair.
@id("specialist-looks-up-any-reservation")
permit(
  principal,
  action == Action::"LookupReservation",
  resource
) when {
  !(context has presented) &&
  ((context has actingFor && context.actingFor in Role::"specialist") ||
   (!(context has actingFor) && principal in Role::"specialist"))
};

// P8 (policy7): A specialist may read any reservation, without a pair.
@id("specialist-reads-any-reservation")
permit(
  principal,
  action == Action::"ReadReservation",
  resource
) when {
  !(context has presented) &&
  ((context has actingFor && context.actingFor in Role::"specialist") ||
   (!(context has actingFor) && principal in Role::"specialist"))
};

// P9 (policy8): A specialist reads public, internal, and confidential
// leaves. Restricted leaves stay nobody's.
@id("specialist-fields-on-any-reservation")
permit(
  principal,
  action == Action::"ReadReservationField",
  resource
) when {
  !(context has presented) &&
  ((context has actingFor && context.actingFor in Role::"specialist") ||
   (!(context has actingFor) && principal in Role::"specialist")) &&
  context has field &&
  Contract::"Reservation".hasTag(context.field) &&
  ["public", "internal", "confidential"].contains(Contract::"Reservation".getTag(context.field))
};

// P10 (policy9): A specialist may update any reservation at object
// level, without a pair; P11 bounds the paths.
@id("specialist-updates-any-reservation")
permit(
  principal,
  action == Action::"UpdateReservation",
  resource
) when {
  !(context has presented) &&
  ((context has actingFor && context.actingFor in Role::"specialist") ||
   (!(context has actingFor) && principal in Role::"specialist"))
};

// P11 (policy10): A specialist writes the paths whose writer is
// "specialist": the remarks. The customer's paths need the pair.
@id("specialist-updates-specialist-fields")
permit(
  principal,
  action == Action::"UpdateReservationField",
  resource
) when {
  !(context has presented) &&
  ((context has actingFor && context.actingFor in Role::"specialist") ||
   (!(context has actingFor) && principal in Role::"specialist")) &&
  context has field &&
  Contract::"Reservation/writers".hasTag(context.field) &&
  Contract::"Reservation/writers".getTag(context.field) == "specialist"
};

// P12 (policy11): A specialist may cancel any reservation, without a
// pair.
@id("specialist-cancels-any-reservation")
permit(
  principal,
  action == Action::"CancelReservation",
  resource
) when {
  !(context has presented) &&
  ((context has actingFor && context.actingFor in Role::"specialist") ||
   (!(context has actingFor) && principal in Role::"specialist"))
};

// P13 (policy12): Listing has no customer form; the specialist's view
// lists.
@id("specialist-lists-reservations")
permit(
  principal,
  action == Action::"ListReservations",
  resource == Collection::"reservations"
) when {
  !(context has presented) &&
  ((context has actingFor && context.actingFor in Role::"specialist") ||
   (!(context has actingFor) && principal in Role::"specialist"))
};

// G1 (policy13): Only an employee is acted for. An exchanged token
// naming a human outside the employee role grants that human nothing
// through the agent; a customer is never a party by identity.
@id("only-employees-are-acted-for")
forbid(
  principal,
  action,
  resource
) when {
  context has actingFor &&
  !(context.actingFor in Role::"employee")
};
