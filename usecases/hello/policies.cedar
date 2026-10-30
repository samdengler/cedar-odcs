// Hello: the smallest use case that shows the whole mechanism.
//
// A note has an owner. The owner may read their own notes; a reviewer
// may read any note. Fields are classified in the contract, and the
// two field policies grant levels: the owner sees public and
// confidential, the reviewer sees public and internal. No policy
// names a field.
//
// The request leg never has the note, so the read is decided on the
// response, on the note the API returns: the request leg asks
// LookupNote, which anyone holds (policy4), and the response leg asks
// ReadNote and ReadNoteField.
//
// Policy ids are positional (policy0, policy1, ...); the corpus refers
// to them.

// policy0: the owner reads their own note.
@id("owner-reads-own-note")
permit(
  principal,
  action == Action::"ReadNote",
  resource
) when {
  resource has owner &&
  resource.owner == principal
};

// policy1: a reviewer reads any note.
@id("reviewer-reads-any-note")
permit(
  principal in Role::"reviewer",
  action == Action::"ReadNote",
  resource
);

// policy2: the owner reads public and confidential fields of their
// own note. The field is looked up in the classification map.
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

// policy3: a reviewer reads public and internal fields of any note.
@id("reviewer-fields-on-any-note")
permit(
  principal in Role::"reviewer",
  action == Action::"ReadNoteField",
  resource
) when {
  context has field &&
  Contract::"Note".hasTag(context.field) &&
  ["public", "internal"].contains(Contract::"Note".getTag(context.field))
};

// policy4: anyone may look up a note; the response decides.
@id("anyone-looks-up-a-note")
permit(
  principal,
  action == Action::"LookupNote",
  resource
);
