# Orders

An order with an owner, a support desk, a finance role, and an
employee acting for a customer: the first ten iterations of this
project on the shared engine. It is step 2 of the learning path, at
[learn/roles.html](../../learn/roles.html), which runs it, compares
three identities, and breaks it on purpose.

A write is decided before the Orders API is called, when the
interceptor has only the call, so `update_order` and `cancel_order`
name the customer they are for, `customerId`, and the policies compare
it with the caller: the customer, or the customer an employee acts
for. Support in direct mode names no one; the role writes any order.
The Orders API must refuse a write whose order the named customer does
not own. No policy can check that: the request leg never has the
order. A read is decided on the response, on the order the API
returned.
