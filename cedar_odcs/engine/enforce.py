"""The two legs of enforcement, for any use case.

  decide_request   the request leg for a Call (see engine/calls.py)
  decide_response  the response leg for a Call: the rows of a list,
                   or the one object
  explain          why a refused call was refused, in the one wording
                   both interfaces use

Both are written in terms of three questions an interface may also
ask directly:

  check_call     the request leg: the verb round, then the payload
                 round for a verb that carries a payload
  filter_rows    the response leg for a list: the row round, then
                 the field round on each surviving row
  filter_object  the response leg for one object

Fields are examined leaf by leaf, by path. A nested object contributes
paths like contact.email; a list of objects contributes index-free
paths like passengers[].seat, and one decision per path applies to
every element. A list holding lists cannot be named and is denied.
Decisions are cached per path within one call, which is iteration 1's
mask: the field round asks Cedar once per distinct path, whatever the
number of rows.

Resource entities are built from the payload. The descriptor says
which fields become attributes and of what type; every other field is
looked up in the tag maps by the field policies.
"""

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import cedarpy

from cedar_odcs.engine.identities import Projection, project
from cedar_odcs.engine.usecase import UseCase

if TYPE_CHECKING:  # calls.py imports this module; the name is for readers
    from cedar_odcs.engine.calls import Call

ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:@/-]+$")


@dataclass
class CallDecision:
    allowed: bool
    denied_verb: bool
    denied_fields: list = field(default_factory=list)


def explain(call: "Call", decision: CallDecision) -> str:
    """Why a call was refused, in one sentence. Both interfaces say it
    in these words: the command line prints it, the interceptor returns
    it as the JSON-RPC error message."""
    verb = call.action.split("::", 1)[1].strip('"')
    if decision.denied_verb:
        return f"{verb} is not permitted for this caller"
    return f"{verb} rejected; fields not permitted: {', '.join(decision.denied_fields)}"


@dataclass
class RowsDecision:
    rows: list
    dropped: list = field(default_factory=list)   # {"position", "id", "reason"}
    stripped: dict = field(default_factory=dict)  # position -> paths removed


class Engine:
    """One use case's policies and facts, asked questions."""

    def __init__(self, use_case: UseCase):
        self.use_case = use_case
        self.policies = use_case.policies
        self.entities = use_case.entities

    def projection(self, claims: dict) -> Projection:
        return project(claims, self.entities)

    def _entities(self, projection: Projection, extra: list) -> str:
        parties = [projection.principal_entity]
        if projection.acted_for_entity is not None:
            parties.append(projection.acted_for_entity)
        replaced = [e["uid"] for e in parties + extra]
        kept = [e for e in self.entities if e["uid"] not in replaced]
        return json.dumps(kept + parties + extra)

    def is_allowed(self, projection: Projection, action: str, resource: str,
                   context: dict = None, extra: list = None) -> bool:
        request = {
            "principal": projection.principal,
            "action": action,
            "resource": resource,
            "context": {**projection.context, **(context or {})},
        }
        result = cedarpy.is_authorized(request, self.policies, self._entities(projection, extra or []))
        return result.decision == cedarpy.Decision.Allow

    # ---- entities from the payload

    def entity_from_row(self, row: dict) -> dict:
        attrs = {}
        for name, cedar_type in self.use_case.attributes.items():
            if name not in row:
                continue
            if cedar_type in ("String", "Long", "Bool"):
                attrs[name] = row[name]
            else:
                attrs[name] = {"__entity": {"type": cedar_type, "id": row[name]}}
        return {
            "uid": {"type": self.use_case.resource_type, "id": row[self.use_case.id_field]},
            "attrs": attrs,
            "parents": [],
        }

    def resource_ref(self, row_id: str) -> str:
        return f'{self.use_case.resource_type}::"{row_id}"'

    # ---- the request leg

    def decide_request(self, claims: dict, call: "Call") -> CallDecision:
        """One tool call on the request leg: the verb round, the
        pre-fetch the verb may need, then the payload round."""
        return self.check_call(claims, call.action, call.resource, call.payload,
                               call.context, row_id=call.row_id)

    def check_call(self, claims: dict, action: str, resource: str,
                   body: dict = None, context: dict = None, row_id: str = None) -> CallDecision:
        projection = self.projection(claims)
        extra = []
        if action in self.use_case.prefetch_actions:
            # The verb needs the record: fetch it through the read path
            # and decide on its attributes. No record, no call.
            record = self.use_case.fetch(row_id) if row_id is not None else None
            if not isinstance(record, dict):
                return CallDecision(allowed=False, denied_verb=True)
            extra = [self.entity_from_row(record)]
        if not self.is_allowed(projection, action, resource, context, extra):
            return CallDecision(allowed=False, denied_verb=True)
        field_action = self.use_case.field_actions.get(action)
        if field_action is None:
            return CallDecision(allowed=True, denied_verb=False)
        if not isinstance(body, dict) or not body:
            return CallDecision(allowed=False, denied_verb=False, denied_fields=["<no payload>"])
        decided = {}

        def allow(path):
            if path not in decided:
                decided[path] = self.is_allowed(
                    projection, field_action, resource, {**(context or {}), "field": path}, extra
                )
            return decided[path]

        denied = []
        _walk(body, "", allow, denied)
        return CallDecision(allowed=not denied, denied_verb=False, denied_fields=sorted(set(denied)))

    # ---- the response leg

    def decide_response(self, claims: dict, call: "Call", payload) -> RowsDecision:
        """The tool's payload, filtered as the tool's returns says: a
        list of rows or one object. A payload of the other shape
        cannot be filtered and is withheld."""
        if call.returns == "list":
            if not isinstance(payload, list):
                raise ValueError("list tool returned no list")
            return self.filter_rows(claims, payload, call.context)
        if not isinstance(payload, dict):
            raise ValueError("object tool returned no object")
        return self.filter_object(claims, payload, call.context)

    def filter_rows(self, claims: dict, rows: list, context: dict = None) -> RowsDecision:
        projection = self.projection(claims)
        kept, dropped, stripped = [], [], {}
        decided = {}
        for position, row in enumerate(rows):
            row_id = row.get(self.use_case.id_field) if isinstance(row, dict) else None
            if not isinstance(row_id, str) or not ID_PATTERN.match(row_id):
                dropped.append({"position": position, "id": None, "reason": "no usable id"})
                continue
            entity = self.entity_from_row(row)
            resource = self.resource_ref(row_id)
            if not self.is_allowed(projection, self.use_case.read_action, resource, context, [entity]):
                dropped.append({"position": position, "id": row_id, "reason": "read denied"})
                continue
            cache = decided.setdefault(_mask_key(entity), {})

            def allow(path, cache=cache, resource=resource, entity=entity):
                if path not in cache:
                    cache[path] = self.is_allowed(
                        projection, self.use_case.read_field_action, resource,
                        {**(context or {}), "field": path}, [entity],
                    )
                return cache[path]

            removed = []
            filtered = _filter(row, "", allow, removed)
            if removed:
                stripped[position] = sorted(set(removed))
            kept.append(filtered)
        return RowsDecision(rows=kept, dropped=dropped, stripped=stripped)

    def filter_object(self, claims: dict, row: dict, context: dict = None) -> RowsDecision:
        return self.filter_rows(claims, [row], context)


def _mask_key(entity: dict) -> str:
    # Field decisions depend on the resource's attributes, never on
    # its id, so rows with the same attributes share one mask.
    return json.dumps(entity["attrs"], sort_keys=True)


def _is_object_list(value) -> bool:
    return isinstance(value, list) and any(isinstance(v, (dict, list)) for v in value)


def _child(path: str, name: str) -> str:
    return f"{path}.{name}" if path else name


def _walk(value, path: str, allow, denied: list) -> None:
    """The payload round: collect every denied leaf path."""
    if isinstance(value, dict):
        for name, child in value.items():
            _walk(child, _child(path, name), allow, denied)
    elif _is_object_list(value):
        if any(not isinstance(v, dict) for v in value):
            denied.append(path)
            return
        for element in value:
            _walk(element, path + "[]", allow, denied)
    elif not allow(path):
        denied.append(path)


def _filter(value, path: str, allow, removed: list):
    """The field round: the value with denied leaves removed."""
    if isinstance(value, dict):
        out = {}
        for name, child in value.items():
            child_path = _child(path, name)
            kept = _filter(child, child_path, allow, removed)
            if kept is not _REMOVED:
                out[name] = kept
        if not out and value:
            # every leaf of a nested object was denied: the object goes
            return _REMOVED
        return out
    if _is_object_list(value):
        if any(not isinstance(v, dict) for v in value):
            removed.append(path)
            return _REMOVED
        out = []
        for element in value:
            kept = _filter(element, path + "[]", allow, removed)
            if kept is not _REMOVED:
                out.append(kept)
        if not out and value:
            # every element lost every leaf: the list goes
            return _REMOVED
        return out
    if allow(path):
        return value
    removed.append(path)
    return _REMOVED


_REMOVED = object()
