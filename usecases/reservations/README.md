# Reservations

A reservation held by whoever presents its record locator and the
holder's last name, with no customer identity, nested passengers and
segments, a specialist role, and the agent as a party of its own. It
is step 3 of the learning path, at
[learn/possession.html](../../learn/possession.html), which runs it
and breaks it on purpose.

A read is decided on the response, on the reservation the API
returned: its locator and holder's last name must be the presented
ones. A write is decided before the Reservations API is called, when
the interceptor has only the call, so the policies require the pair
and bound the paths a holder may set. The Reservations API must
refuse a write whose locator and last name do not name a reservation;
no policy can check that, because the request leg never has the
reservation.
