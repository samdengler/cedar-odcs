"""The projection from token claims to a Cedar request.

The bearer token that reaches the Gateway names the parties; this
module turns its claims into the principal, the mode, and the entity
facts about the principal that the policies read. Nothing here looks
anything up: every fact comes from the token.

The mapping follows RFC 8693, OAuth 2.0 Token Exchange. In a delegated
token the subject (`sub`) is the party on whose behalf the request is
made and the actor claim (`act`) names the party making it. The Cedar
principal is always the actor, so:

  no act claim:   principal = User::sub,      direct mode
  act claim:      principal = User::act.sub,  context.actingFor = User::sub

Role membership comes from a `roles` claim on the actor. The principal
entity is built per request with those roles as parents, so the
policies' `principal in Role::"support"` reads the token, not a store.

Every claim this module reads is an assumption about the identity
setup until confirmed against a real token; the design document lists
them. tokens/*.json are hand-written payloads standing in for decoded
tokens, one per mode.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import cedarpy

HERE = Path(__file__).parent

ROLE_CLAIM = "roles"


@dataclass
class Projection:
    principal: str            # Cedar entity ref of the actor
    context: dict             # actingFor when delegated, else empty
    principal_entity: dict    # the actor with role parents, from the token
    mode: str                 # "customer-direct", "employee-direct", "employee-for-customer"


@dataclass
class Decision:
    allowed: bool
    determining_policies: list


def _user(sub: str) -> str:
    return f'User::"{sub}"'


def _entity_ref(sub: str) -> dict:
    return {"__entity": {"type": "User", "id": sub}}


def project(claims: dict) -> Projection:
    """Claims of a decoded, already verified token, to the Cedar parties."""
    act = claims.get("act")
    if act is None:
        actor_sub = claims["sub"]
        roles = claims.get(ROLE_CLAIM, [])
        context = {}
        mode = "employee-direct" if roles else "customer-direct"
    else:
        actor_sub = act["sub"]
        roles = act.get(ROLE_CLAIM, [])
        context = {"actingFor": _entity_ref(claims["sub"])}
        mode = "employee-for-customer"
    principal_entity = {
        "uid": {"type": "User", "id": actor_sub},
        "attrs": {},
        "parents": [{"type": "Role", "id": role} for role in roles],
    }
    return Projection(_user(actor_sub), context, principal_entity, mode)


def load_policies() -> str:
    return (HERE / "policies.cedar").read_text()


def load_entities() -> list:
    return json.loads((HERE / "entities.json").read_text())


def is_allowed(claims: dict, action: str, resource: str, extra_context: dict = None) -> Decision:
    """One authorization question asked with a token instead of a principal.

    The principal entity from the token replaces any stored entity of
    the same id: what the token says about the actor's roles is what
    the policies see.
    """
    projection = project(claims)
    stored = [e for e in load_entities() if e["uid"] != projection.principal_entity["uid"]]
    entities = json.dumps(stored + [projection.principal_entity])
    request = {
        "principal": projection.principal,
        "action": action,
        "resource": resource,
        "context": {**projection.context, **(extra_context or {})},
    }
    result = cedarpy.is_authorized(request, load_policies(), entities)
    return Decision(
        allowed=(result.decision == cedarpy.Decision.Allow),
        determining_policies=list(result.diagnostics.reasons),
    )
