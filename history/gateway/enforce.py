"""Every enforcement move from iterations 1 through 9, in one module.

The interceptor handlers in interceptor.py are thin: they parse the
Gateway's event, decode the token, name the verb and the resource,
and call one of the three functions here. Each function is the
wrapper an earlier iteration built, asked with a token's projection
instead of a bare principal:

  check_call    iteration 5's request leg: the verb round, then the
                payload round for an update (iterations 2 and 4)
  filter_fields iteration 3's response leg for one object, with the
                entity built from the payload (iteration 9)
  filter_rows   iteration 9's response leg for a list

The policies and entities are row-filtering/policies.cedar and the
contract build's entities.json, byte for byte; test_interceptor.py
checks that. Nothing here is new governance; it is the governance
already tested and proven, reached from a Gateway event.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import cedarpy

from bearer import Projection, load_entities, load_policies, project

HERE = Path(__file__).parent

# Verbs whose payload gets the per-field round.
FIELD_ACTIONS = {'Action::"UpdateOrder"': 'Action::"UpdateOrderField"'}

# The entity-typed attributes of a row, from the contract build:
# contract/generated/order.entities.cedarschema.
ATTRIBUTES = {"owner": "User"}


@dataclass
class CallDecision:
    allowed: bool
    denied_verb: bool
    denied_fields: list = field(default_factory=list)


@dataclass
class RowsDecision:
    rows: list
    dropped: list = field(default_factory=list)   # {"position", "id", "reason"} per row removed
    stripped: dict = field(default_factory=dict)  # position -> fields removed


# Read once per process, as in iteration 9.
POLICIES = load_policies()
ENTITIES = load_entities()
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:@/-]+$")


def _entities(projection: Projection, extra: list = None) -> str:
    # The token's principal and the payload's rows replace stored
    # entities with the same uid, type and id both; an Order and a
    # Contract that share an id string are different entities.
    replaced = [projection.principal_entity["uid"]] + [e["uid"] for e in (extra or [])]
    kept = [e for e in ENTITIES if e["uid"] not in replaced]
    return json.dumps(kept + [projection.principal_entity] + (extra or []))


def is_allowed(projection: Projection, action: str, resource: str, context: dict = None, extra: list = None) -> bool:
    request = {
        "principal": projection.principal,
        "action": action,
        "resource": resource,
        "context": {**projection.context, **(context or {})},
    }
    result = cedarpy.is_authorized(request, POLICIES, _entities(projection, extra))
    return result.decision == cedarpy.Decision.Allow


UNNAMEABLE = object()


def leaves(value, prefix: str = "") -> dict:
    """Every leaf of a payload by dotted path: {"shippingAddress.street": ...}.

    The field rounds ask one question per leaf, so a value nested
    under an allowed field is never carried along unexamined. A list
    of scalars is one leaf. A list that holds an object cannot be
    named leaf by leaf and is returned as UNNAMEABLE, which both
    rounds treat as denied.
    """
    out = {}
    if isinstance(value, dict):
        for name, child in value.items():
            path = f"{prefix}.{name}" if prefix else str(name)
            out.update(leaves(child, path))
        return out
    if isinstance(value, list) and any(isinstance(item, (dict, list)) for item in value):
        return {prefix: UNNAMEABLE}
    return {prefix: value}


def assemble(kept: dict) -> dict:
    """The inverse of leaves for the leaves that survived."""
    out = {}
    for path, value in kept.items():
        node = out
        parts = path.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return out


def check_call(claims: dict, action: str, resource: str, body: dict = None) -> CallDecision:
    """The request leg: verb round, then payload round for an update."""
    projection = project(claims)
    if not is_allowed(projection, action, resource):
        return CallDecision(allowed=False, denied_verb=True)
    field_action = FIELD_ACTIONS.get(action)
    if field_action is None:
        return CallDecision(allowed=True, denied_verb=False)
    if not isinstance(body, dict) or not body:
        # A write with no fields to check is not forwarded: the payload
        # round is the only thing that bounds a role-granted update.
        return CallDecision(allowed=False, denied_verb=False, denied_fields=["<no payload>"])
    denied = [
        path for path, value in leaves(body).items()
        if value is UNNAMEABLE or not is_allowed(projection, field_action, resource, {"field": path})
    ]
    return CallDecision(allowed=not denied, denied_verb=False, denied_fields=denied)


def entity_from_row(row: dict) -> dict:
    attrs = {
        name: {"__entity": {"type": entity_type, "id": row[name]}}
        for name, entity_type in ATTRIBUTES.items()
        if name in row
    }
    return {"uid": {"type": "Order", "id": row["id"]}, "attrs": attrs, "parents": []}


def filter_fields(projection: Projection, row: dict) -> tuple:
    """(the row reduced to readable fields, the fields removed)."""
    entity = entity_from_row(row)
    resource = f'Order::"{row["id"]}"'
    kept, removed = {}, []
    for path, value in leaves(row).items():
        if value is not UNNAMEABLE and is_allowed(
            projection, 'Action::"ReadOrderField"', resource, {"field": path}, [entity]
        ):
            kept[path] = value
        else:
            removed.append(path)
    return assemble(kept), removed


def filter_rows(claims: dict, rows: list) -> RowsDecision:
    """The response leg for a list: rows the caller may read, each reduced."""
    projection = project(claims)
    kept, dropped, stripped = [], [], {}
    for position, row in enumerate(rows):
        row_id = row.get("id") if isinstance(row, dict) else None
        if not isinstance(row_id, str) or not ID_PATTERN.match(row_id):
            dropped.append({"position": position, "id": None, "reason": "no usable id"})
            continue
        entity = entity_from_row(row)
        if not is_allowed(projection, 'Action::"ReadOrder"', f'Order::"{row_id}"', None, [entity]):
            dropped.append({"position": position, "id": row_id, "reason": "ReadOrder denied"})
            continue
        allowed_row, removed = filter_fields(projection, row)
        if removed:
            stripped[position] = removed
        kept.append(allowed_row)
    return RowsDecision(rows=kept, dropped=dropped, stripped=stripped)


def filter_object(claims: dict, row: dict) -> RowsDecision:
    """The response leg for one object: the same as a one-row list."""
    return filter_rows(claims, [row])
