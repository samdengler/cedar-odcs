"""The descriptor a use case hands the engine, and where its files are.

A use case folder is read in one of two shapes. The shape of a use
case (designs/reorganization.md) gathers the build's inputs and
outputs under `contract/` and the fixtures under `tests/`; the older
shape keeps both at the root. `layout()` tells them apart by the one
directory only the new shape has, `contract/`, and `paths()` is what
every reader asks for a directory, so the two spellings live here and
nowhere else.

    new                              old
    contract/unity/                  unity/
    contract/<stem>.odcs.yaml        <stem>.odcs.yaml
    contract/generated/              generated/
    tests/test-cases/                tests/
    tests/identities/                callers/
    tests/responses/                 records/
    tests/events/                    events/

Everything else, policies.cedar, facts.json, entities.json, and the
two hand-written schemas, is at the root in both.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from cedar_odcs.engine.identities import ClaimsMapping


def layout(root) -> str:
    """"new" for a use case folder with a contract/ directory, else "old"."""
    return "new" if (Path(root) / "contract").is_dir() else "old"


@dataclass(frozen=True)
class Paths:
    """Where one use case keeps each kind of file, in either shape."""

    root: Path
    layout: str

    @property
    def contract_dir(self) -> Path:
        """What the build writes into: contract/ in the new shape, the root in the old."""
        return self.root / "contract" if self.layout == "new" else self.root

    @property
    def unity(self) -> Path:
        return self.contract_dir / "unity"

    @property
    def generated(self) -> Path:
        return self.contract_dir / "generated"

    @property
    def test_cases(self) -> Path:
        return self.root / "tests" / "test-cases" if self.layout == "new" else self.root / "tests"

    @property
    def identities(self) -> Path:
        return self.root / "tests" / "identities" if self.layout == "new" else self.root / "callers"

    @property
    def responses(self) -> Path:
        return self.root / "tests" / "responses" if self.layout == "new" else self.root / "records"

    @property
    def events(self) -> Path:
        return self.root / "tests" / "events" if self.layout == "new" else self.root / "events"

    def relative(self, path: Path) -> str:
        """A path under the root as the build's output keys spell it."""
        return path.relative_to(self.root).as_posix()


def paths(root) -> Paths:
    root = Path(root)
    return Paths(root, layout(root))


def policies_text(root, name: str = "policies.cedar") -> str:
    """A use case's policies as Cedar text: the named file, and, for the
    use case's own policies.cedar, the field policies the build rendered
    from grants.yaml (generated/grants.cedar) when there are any."""
    place = paths(root)
    text = (place.root / name).read_text()
    grants = place.generated / "grants.cedar"
    if name == "policies.cedar" and grants.is_file():
        text = text.rstrip("\n") + "\n\n" + grants.read_text()
    return text


@dataclass
class UseCase:
    name: str
    root: Path
    # The Cedar entity type a payload row becomes, e.g. "Order".
    resource_type: str
    # Payload field to Cedar type for the fields that become attributes
    # of the resource entity: {"owner": "User"} or {"holderLastName": "String"}.
    # Every other field is looked up in the tag maps and never becomes
    # an attribute. Entity types produce entity references; "String",
    # "Long", and "Bool" produce values.
    attributes: dict
    # The payload field that is the row's id.
    id_field: str
    # The response-leg verbs: the row question and the field question.
    read_action: str
    read_field_action: str
    # Request-leg verbs whose payload gets the field round: verb to
    # field verb, e.g. {'Action::"UpdateOrder"': 'Action::"UpdateOrderField"'}.
    field_actions: dict
    # MCP tool name to how the handlers treat it (see cedar_odcs.gateway.handlers).
    # No verb needs the record on the request leg: a read decides on
    # the response, a write on what the call names.
    tools: dict = field(default_factory=dict)
    # Which token claims name the subject, the roles, and the actor
    # (cedar_odcs.engine.identities). The default reads sub, roles, act.
    claims: ClaimsMapping = ClaimsMapping()

    @property
    def policies(self) -> str:
        return policies_text(self.root)

    @property
    def entities(self) -> list:
        return json.loads((self.root / "entities.json").read_text())
