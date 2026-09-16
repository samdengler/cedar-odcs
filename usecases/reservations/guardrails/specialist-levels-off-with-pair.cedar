// Guardrail: while a pair is presented, internal leaves are never
// read, whoever the specialist is. Presenting a pair means being held
// to the customer's view.
//
// A first version joined this with the write-side rule below in one
// forbid over both field verbs; the prover refused it, because the
// disjunction also forbade a possession read of a public leaf whose
// writer is the specialist. One guardrail per verb.
@id("guardrail-specialist-levels-off-with-pair")
forbid(
  principal,
  action == Action::"ReadReservationField",
  resource
) when {
  context has presented &&
  context has field &&
  Contract::"Reservation".hasTag(context.field) &&
  Contract::"Reservation".getTag(context.field) == "internal"
};
