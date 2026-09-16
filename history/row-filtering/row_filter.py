"""The response leg for list endpoints: rows, then fields.

A list call returns many orders. On the request leg the verb round
allows the call for anyone; the governance is here, on the response.
For each row the wrapper asks the question iteration 1 asked of a
single order:

  may User::"alice" ReadOrder Order::"order-2002"?

and drops the rows that come back Deny. Each surviving row then gets
iteration 3's per-field round, and denied fields are stripped.

The resource entity for each row is built from the row itself. The
response leg has the data in hand, so there is no store to ask: the
payload field that the contract marks as an entity reference (owner,
from `entity Order { owner: User }` in contract/generated/) becomes
the attribute the ownership policies read. A row with no usable id
cannot be an entity and is dropped before any question is asked. A
row with no owner is decided without ownership: the ownership
policies error on it, which is a Deny, so a customer loses the row,
while a role that reads any order keeps it. Every removal is reported
with the row's position, its id when it had one, and the reason.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import cedarpy

HERE = Path(__file__).parent

# The entity-typed attributes of a row, as the contract declares them:
# contract/generated/order.entities.cedarschema says
# `entity Order { owner: User };`. Every other field is looked up in
# the tag maps by the field policies and never becomes an attribute.
ATTRIBUTES = {"owner": "User"}


@dataclass
class Decision:
    allowed: bool
    determining_policies: list
    errors: list


@dataclass
class RowsDecision:
    rows: list                                   # what the caller receives
    dropped: list = field(default_factory=list)  # {"position", "id", "reason"} per row removed
    stripped: dict = field(default_factory=dict) # position -> fields removed


# Read once per process: the policies and the built entities do not
# change between requests, and the response leg asks many questions.
POLICIES = (HERE / "policies.cedar").read_text()
ENTITIES = json.loads((HERE / "entities.json").read_text())

# An id is interpolated into a Cedar entity reference, so it may hold
# nothing the reference syntax could misread.
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:@/-]+$")


def load_policies() -> str:
    return POLICIES


def load_entities() -> list:
    return ENTITIES


def entity_from_row(row: dict) -> dict:
    attrs = {
        name: {"__entity": {"type": entity_type, "id": row[name]}}
        for name, entity_type in ATTRIBUTES.items()
        if name in row
    }
    return {"uid": {"type": "Order", "id": row["id"]}, "attrs": attrs, "parents": []}


def is_allowed(principal: str, action: str, resource: str, entities: list, context: dict = None) -> Decision:
    request = {"principal": principal, "action": action, "resource": resource, "context": context or {}}
    result = cedarpy.is_authorized(request, load_policies(), json.dumps(entities))
    return Decision(
        allowed=(result.decision == cedarpy.Decision.Allow),
        determining_policies=list(result.diagnostics.reasons),
        errors=list(result.diagnostics.errors),
    )


def filter_rows(principal: str, rows: list, context: dict = None) -> RowsDecision:
    """Rows the caller may read, each reduced to the fields they may read.

    principal is a Cedar entity ref, e.g. 'User::"alice"'. context
    carries actingFor in on behalf of mode.
    """
    context = context or {}
    stored = load_entities()
    kept, dropped, stripped = [], [], {}
    for position, row in enumerate(rows):
        row_id = row.get("id") if isinstance(row, dict) else None
        if not isinstance(row_id, str) or not ID_PATTERN.match(row_id):
            dropped.append({"position": position, "id": None, "reason": "no usable id"})
            continue
        entity = entity_from_row(row)
        # The row is the fact; a stored order of the same id is replaced.
        entities = [e for e in stored if e["uid"] != entity["uid"]] + [entity]
        resource = f'Order::"{row_id}"'
        if not is_allowed(principal, 'Action::"ReadOrder"', resource, entities, context).allowed:
            dropped.append({"position": position, "id": row_id, "reason": "ReadOrder denied"})
            continue
        allowed_row, removed = {}, []
        for name, value in row.items():
            field_context = {**context, "field": name}
            if is_allowed(principal, 'Action::"ReadOrderField"', resource, entities, field_context).allowed:
                allowed_row[name] = value
            else:
                removed.append(name)
        if removed:
            stripped[position] = removed
        kept.append(allowed_row)
    return RowsDecision(rows=kept, dropped=dropped, stripped=stripped)
