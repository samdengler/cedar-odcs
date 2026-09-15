# Learn cedar-osdc

A path in three steps, each a complete use case you can run, change,
and break. It starts where Cedar's own tutorial ends: you can write a
`permit`, an entity, and a schema, and you want to know how those
become data governance for an agent's tool calls.

Before step 1, read Cedar's first-time sequence, in the order the docs
recommend: [terms and concepts](https://docs.cedarpolicy.com/overview/terminology.html),
the [example scenario](https://docs.cedarpolicy.com/overview/scenario.html),
[basic syntax](https://docs.cedarpolicy.com/policies/syntax-policy.html),
and the [schema overview](https://docs.cedarpolicy.com/schema/schema.html).
The [TinyTodo tutorial](https://github.com/cedar-policy/cedar-examples/tree/main/tinytodo)
is the hands-on version. Twenty minutes is enough.

Then, from the repository root, with [uv](https://docs.astral.sh/uv/)
installed:

```sh
uv sync
uv run cedar-osdc run-tests learn/hello
```

| Step | What you learn | Runs against | Cedar pages it assumes |
|---|---|---|---|
| [1. Hello](hello/README.md) | a contract classifies fields, policies grant levels, the response leg strips the rest | `learn/hello` | terms, syntax |
| [2. Roles, verbs, and acting for someone](roles.md) | roles hold verbs, a payload is checked field by field, an employee acts for a customer | `usecases/orders` | schema, [entity tags](https://docs.cedarpolicy.com/policies/syntax-entity.html), [validation](https://docs.cedarpolicy.com/policies/validation.html) |
| [3. Possession, nesting, and three parties](possession.md) | a credential presented in context, a check that waits for the record, nested paths, the agent as a party | `usecases/reservations` | [entities and context JSON](https://docs.cedarpolicy.com/auth/entities-syntax.html) |

Every step ends with a change that makes a test fail, because that
loop is the method: attacks are recorded before defenses, and a
defense weakened later fails a test.

Beside the path:

- [The guide](guide.md): what you need to know about your own domain
  to fill in a use case, the three policy shapes, and the command line.
- [How the proofs are used, and what they do not cover](proofs.md).
- [Cedar's playground](https://www.cedarpolicy.com/en/playground):
  `cedar-osdc share` opens any case there.

What is not here yet: scaffolding a use case of your own with
`cedar-osdc new`, and building from a plain list of fields instead of
a Unity Catalog export. Until then, copy `learn/hello` and edit; the
guide says what to change.
