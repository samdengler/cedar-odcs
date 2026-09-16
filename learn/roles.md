# Step 2: Roles, verbs, and acting for someone

The orders use case is the first ten iterations of this project, on
the shared core. It adds three things to hello: roles that hold verbs,
a payload checked field by field before a write is forwarded, and an
employee acting for a customer.

Cedar pages this step assumes: the schema overview,
[entity tags](https://docs.cedarpolicy.com/policies/syntax-entity.html)
(the `hasTag` and `getTag` the field policies use), and
[policy validation](https://docs.cedarpolicy.com/policies/validation.html).

## Run it

```sh
uv run cedar-osdc run-tests usecases/orders
```

Seventy-five cases, carried from nine iterations. Then compare what
three callers may do on bob's order:

```sh
uv run cedar-osdc check-access usecases/orders --caller usecases/orders/callers/alice.json
uv run cedar-osdc check-access usecases/orders --caller usecases/orders/callers/carol.json
uv run cedar-osdc check-access usecases/orders --caller usecases/orders/callers/dave.json
```

Alice, a customer, holds no verb on an order she does not own. Carol,
on the support desk, reads any order, cancels any order, updates any
order, and may set exactly one field, `internalNotes`. Dave in finance
holds `RefundOrder` and nothing else: not even a read, because a verb
held implies no other.

## Verbs belong to roles

```cedar
@id("finance-refunds-any-order")
permit(
  principal in Role::"finance",
  action == Action::"RefundOrder",
  resource
) when {
  !(context has actingFor)
};
```

Try the refund as alice, who owns the order:

```sh
uv run cedar-osdc dry-run usecases/orders --caller usecases/orders/callers/alice.json \
    --tool orders___refund_order --arg orderId=order-1001
```

Rejected: ownership grants no refund. That is OWASP's broken function
level authorization, met by the absence of a policy.

## A write is checked field by field

Carol may update any order, but the writers map bounds what she may
set. Put a payload through the request leg:

```sh
uv run cedar-osdc dry-run usecases/orders --caller usecases/orders/callers/carol.json \
    --tool orders___update_order --arg orderId=order-2002 \
    --arg 'changes={"internalNotes": "called back", "shippingAddress": "9 Elm St"}'
```

Rejected whole, naming `shippingAddress`. The object-level permit let
the role in; the writers map says which fields are behind the door. A
payload with a field the contract never declared, `isAdmin` say, is
refused the same way: mass assignment fails closed.

## Acting for a customer

Carol acting for alice holds alice's access, and her own role is off:

```sh
uv run cedar-osdc check-access usecases/orders --caller usecases/orders/callers/carol-for-alice.json
```

The confidential fields of alice's order are readable, the internal
ones are not, and bob's order is out of reach. The token is an
exchanged one: alice is its subject, carol its actor, and the
projection in `cedar_osdc/engine/identities.py` turns that into a principal and an
`actingFor` in context.

## Break it

Open `usecases/orders/unity/orders.column_tags.json`, find the
`internal_notes` column, and change its `writer` tag from `support` to
`system`. Rebuild and rerun:

```sh
uv run cedar-osdc build usecases/orders
uv run cedar-osdc run-tests usecases/orders
```

The case "support agent updates internalNotes on any order" fails.
Put it back. Then the harder one: in `policies.cedar`, delete the
line `!(context has actingFor) &&` from `support-fields-on-any-order`
and run the tests. Carol acting for alice now reads alice's internal
notes, and the case that pinned the acting mode fails. If you have
Rust and cvc5 installed, `uv run cedar-osdc prove` fails the same
edit against every possible request, not just the one the corpus
sampled; the proofs page explains what that adds.

## Where to read more

Iterations [1](../bola-reads/design.html) through
[10](../gateway/design.html) each tell how one of these rules came to
be, tests first. Iteration [5](../function-level/design.html) is the
verbs, [4](../field-writes/design.html) the payload round, and
[6](../on-behalf-of/design.html) the acting mode.

Next: [step 3, possession, nesting, and three parties](possession.md).
