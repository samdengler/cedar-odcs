# Step 3: Possession, nesting, and three parties

The reservations use case was built to pressure test the mechanism.
A reservation is held by whoever presents its record locator and the
holder's last name; there is no customer identity at all. The record
is nested, a write cannot be decided until the record has been read,
and a specialist reaches the tools through the agent.

Cedar pages this step assumes:
[entities and context JSON](https://docs.cedarpolicy.com/auth/entities-syntax.html),
since the presented pair travels in context and the record becomes an
entity from the payload.

## Run it

```sh
uv run cedar-osdc run-tests usecases/reservations
```

Forty-three cases. Then the customer's view, which is nobody's
identity and only the pair:

```sh
uv run cedar-osdc check-access usecases/reservations --caller usecases/reservations/tests/identities/agent.json \
    --presented locator=ABC123 --presented lastName=Smith
```

The token is the agent's own, a workload identity; the customer is
the two presented facts. The record's leaves are readable by path,
`passengers[].seat` and `contact.email` among them, and the passport
numbers and medical requests are not, for anyone.

## The check waits for the record

```cedar
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
```

Nothing about the pair can be checked before the record exists, so a
read is decided on the response leg against the record that came
back. Try a wrong name:

```sh
uv run cedar-osdc dry-run usecases/reservations --caller usecases/reservations/tests/identities/agent.json \
    --tool reservations___get_reservation --arg recordLocator=ABC123 --arg lastName=Jones \
    --response usecases/reservations/tests/responses/ABC123.json
```

The lookup is forwarded, the record comes back, the name does not
match, and the customer receives an empty object.

A write cannot wait. Cancel with the wrong name:

```sh
uv run cedar-osdc dry-run usecases/reservations --caller usecases/reservations/tests/identities/agent.json \
    --tool reservations___cancel_reservation --arg recordLocator=ABC123 --arg lastName=Jones
```

Rejected before anything is forwarded: the request leg fetched the
record first, through the read path, and decided on it. The
descriptor names the verbs that need this, and the fetch function
that supplies the record.

## Three parties

```sh
uv run cedar-osdc check-access usecases/reservations --caller usecases/reservations/tests/identities/sam-through-agent.json
```

The token is an exchanged one: the specialist is its subject, the
agent its actor. The agent is the principal, typed `Agent`; the
specialist is the acted-for human whose roles decide; the specialist
reads the remarks, writes them, and lists reservations. Add the pair:

```sh
uv run cedar-osdc check-access usecases/reservations --caller usecases/reservations/tests/identities/sam-through-agent.json \
    --presented locator=ABC123 --presented lastName=Smith
```

The specialist's view is off. Presenting a pair means working the
customer's case and being held to the customer's view.

## Break it

In `usecases/reservations/policies.cedar`, remove the line
`!(context has presented) &&` from `specialist-fields-on-any-reservation`
and run the tests. The case "a specialist presenting a pair does not
read remarks" fails. With Rust and cvc5, `uv run cedar-osdc prove`
also fails the guardrail "specialist levels off with pair", over every
record and every tag map at once.

Then a contract change: in `usecases/reservations/contract/unity/reservations.column_tags.json`,
change the `passengers` column's `classification__passport_number`
from `restricted` to `confidential`, rebuild, and run `check-access`
for the pair. Passport numbers are now readable by possession, and
the corpus case that said restricted stays nobody's fails.

## Where to read more

Iterations [11](../history/reservations-11.html),
[12](../history/reservations-12.html), and
[13](../history/reservations-13.html), and the
[writeup](../history/what-reservations-changed.html) of what this use
case changed in the shared core.

You have now seen everything the mechanism does. The
[guide](guide.md) says how to fill in a use case of your own.
