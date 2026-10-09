# History

This directory is how the project was built. Nine snapshots sit here
under the names they were built with, from `bola-reads` through
`gateway`, each one a standalone uv project with its own policies,
entities, test corpus, and design narrative; `uv run --project
history/<name> pytest history/<name>` runs any of them on its own, and
the root `uv run pytest` collects them all. `index.html` is the timeline of all
fifteen iterations and links to every narrative: the nine `design.html`
pages inside the snapshots, `provable-composition.html` for the
symbolic analysis, `reservations-11.html` through `reservations-13.html`
for the reservation use case, `command-line-14.html` for the
`cedar-odcs` command, `learning-path-15.html` for the learning path,
and `what-reservations-changed.html` for what a second use case changed
in the mechanism. `chain/` holds what the proofs read that no single
iteration owns: the hand-written schemas, the behavioral specs, the
declared revisions, the direct-mode restriction, and the five retired
guardrails. `uv run cedar-odcs prove` proves each snapshot in turn and
each one's decisions against its predecessor's.

Nothing here is the live code. The tool is `cedar_odcs/`, the use cases
are `usecases/`, and those are what the command line, the Gateway
handlers, and `check.sh` run. A snapshot is read by the proofs and by
the parity tests in `usecases/orders/tests/`, which pin the live orders
use case to iteration 9's policies and iteration 7's build output byte
for byte. Change a policy here and a proof or a parity test fails,
which is the point: the snapshots are the record the chain is proven
against.

The snapshot corpora name their policies `policy0`, `policy1`, and so
on, by position in the file, while the live use cases name them by
their `@id` annotation. The snapshots are kept as they were built, and
positional names are the format the corpus runner used through
iteration 10. The reorganization changed the live format so a test case
names the policy it expects rather than counting down the file; the
change stops at the boundary of this directory.
