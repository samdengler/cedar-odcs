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
    dropped: list = field(default_factory=list)
    stripped: dict = field(default_factory=dict)


def _entities(projection: Projection, extra: list = None) -> str:
    stored = load_entities()
    replaced = {projection.principal_entity["uid"]["id"]} | {e["uid"]["id"] for e in (extra or [])}
    kept = [e for e in stored if e["uid"]["id"] not in replaced]
    return json.dumps(kept + [projection.principal_entity] + (extra or []))


def is_allowed(projection: Projection, action: str, resource: str, context: dict = None, extra: list = None) -> bool:
    request = {
        "principal": projection.principal,
        "action": action,
        "resource": resource,
        "context": {**projection.context, **(context or {})},
    }
    result = cedarpy.is_authorized(request, load_policies(), _entities(projection, extra))
    return result.decision == cedarpy.Decision.Allow


def check_call(claims: dict, action: str, resource: str, body: dict = None) -> CallDecision:
    """The request leg: verb round, then payload round for an update."""
    projection = project(claims)
    if not is_allowed(projection, action, resource):
        return CallDecision(allowed=False, denied_verb=True)
    field_action = FIELD_ACTIONS.get(action)
    if field_action is None or not body:
        return CallDecision(allowed=True, denied_verb=False)
    denied = [
        name for name in body
        if not is_allowed(projection, field_action, resource, {"field": name})
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
    for name, value in row.items():
        if is_allowed(projection, 'Action::"ReadOrderField"', resource, {"field": name}, [entity]):
            kept[name] = value
        else:
            removed.append(name)
    return kept, removed


def filter_rows(claims: dict, rows: list) -> RowsDecision:
    """The response leg for a list: rows the caller may read, each reduced."""
    projection = project(claims)
    kept, dropped, stripped = [], [], {}
    for position, row in enumerate(rows):
        if "id" not in row:
            dropped.append(f"row {position}: no id")
            continue
        entity = entity_from_row(row)
        if not is_allowed(projection, 'Action::"ReadOrder"', f'Order::"{row["id"]}"', None, [entity]):
            dropped.append(row["id"])
            continue
        allowed_row, removed = filter_fields(projection, row)
        if removed:
            stripped[row["id"]] = removed
        kept.append(allowed_row)
    return RowsDecision(rows=kept, dropped=dropped, stripped=stripped)


def filter_object(claims: dict, row: dict) -> RowsDecision:
    """The response leg for one object: the same as a one-row list."""
    return filter_rows(claims, [row])
