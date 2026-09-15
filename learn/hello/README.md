# Step 1: Hello

A note has an owner. The owner may read their own notes and a reviewer
may read any note. Each field of a note has a level, and the policies
grant levels: the owner sees public and confidential fields, the
reviewer sees public and internal ones. That is the whole mechanism,
on the smallest example that shows all of it.

Cedar pages this step assumes: terms and concepts, basic syntax.

## Run it

```sh
uv run cedar-osdc run-tests learn/hello
```

Nine cases pass. Each is a Cedar authorization request with the
decision it should get, in `tests/hello.json`. Now ask what each
caller may do:

```sh
uv run cedar-osdc check-access learn/hello --caller learn/hello/callers/ada.json
uv run cedar-osdc check-access learn/hello --caller learn/hello/callers/rae.json
```

Ada, the owner, reads the body and not the reviewer's notes. Rae, the
reviewer, reads the reviewer's notes and not the body. Then put one
tool call through the two legs, without calling any tool:

```sh
uv run cedar-osdc dry-run learn/hello --caller learn/hello/callers/rae.json \
    --tool notes___get_note --arg noteId=note-1 --response learn/hello/note-1.json
```

The request leg forwards the call; the response leg strips `body`
before the note goes back. That is what the two Gateway interceptors
do in production, with the same code.

## What is in the directory

| File | What it is |
|---|---|
| `unity/notes.table.json`, `unity/notes.column_tags.json` | the source of truth: a table's columns and their tags, as Unity Catalog returns them |
| `note.odcs.yaml` | the data contract generated from those, ODCS v3.2.0 |
| `generated/contract.entities.json` | the classification map and the writers map, generated from the contract |
| `generated/note.cedarschema` | the Cedar schema, generated |
| `facts.json` | the sample users, the role, and two notes |
| `entities.json` | facts plus the generated maps, what the policies read |
| `policies.cedar` | four policies; no policy names a field |
| `tests/hello.json` | nine cases in the cedar-integration-tests format |
| `callers/ada.json`, `callers/rae.json` | a caller file each: the claims of that caller's credential, standing in for a decoded, verified JWT |
| `usecase.py` | the descriptor: entity type, which field is the owner, the verbs, the tool table |

The policies never name a field. They look the field up in the map
the contract generated:

```cedar
@id("owner-fields-on-own-note")
permit(
  principal,
  action == Action::"ReadNoteField",
  resource
) when {
  resource has owner &&
  resource.owner == principal &&
  context has field &&
  Contract::"Note".hasTag(context.field) &&
  ["public", "confidential"].contains(Contract::"Note".getTag(context.field))
};
```

So a field's level is data, set by whoever tags the column, and
reviewed as a diff of the generated map; granting a level to a role is
a policy change.

## Break it

Open `unity/notes.column_tags.json` and change the `body` column's
classification from `confidential` to `internal`. Rebuild and rerun:

```sh
uv run cedar-osdc build learn/hello
uv run cedar-osdc run-tests learn/hello
```

Two cases fail: ada can no longer read her own body, and rae now can.
The corpus recorded who may read what before the tag changed, so the
tag change fails a test instead of quietly moving a field between
readers. Put the tag back and rebuild.

Then try the other direction: add a field. Give the table a new
column, tag it `public`, rebuild, and run `check-access` again. The
field is on for both callers with no policy edit, because the map
grew and the policies read the map.

## See it in Cedar's playground

```sh
uv run cedar-osdc share learn/hello --case "rae may not read the body"
```

Open the link. The playground shows the same request, entities, and
policies, and evaluates to denied. Edit the reviewer's field policy
there to include `"confidential"` and evaluate again.

Next: [step 2, roles, verbs, and acting for someone](../roles.md).
