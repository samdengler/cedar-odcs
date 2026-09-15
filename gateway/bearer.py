"""The projection from token claims to a Cedar request, from iteration 6.

Two changes for the interceptor: claims_of decodes the bearer token
the Gateway forwards, and the authorization question itself moved to
enforce.py, which asks it with the projection's parties. The module
is named bearer rather than claims because the root test run imports
every iteration's modules into one process, and iteration 6 already
owns the name claims.

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

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent

ROLE_CLAIM = "roles"


@dataclass
class Projection:
    principal: str            # Cedar entity ref of the actor
    context: dict             # actingFor when delegated, else empty
    principal_entity: dict    # the actor with role parents, from the token
    mode: str                 # "customer-direct", "employee-direct", "employee-for-customer"


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


def _b64url(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def claims_of(bearer: str) -> dict:
    """The payload of a JWT the Gateway has already verified.

    The interceptor sees the raw Authorization header and nothing
    parsed; the signature, issuer, audience, and expiry were checked
    by the Gateway's JWT authorizer before the interceptor ran, so the
    payload is decoded here without re-verifying. That trust holds
    only for the token the Gateway validated, which is why the
    interceptor reads it from the request the Gateway forwarded and
    from nowhere else.
    """
    token = bearer.split(" ", 1)[1] if bearer.lower().startswith("bearer ") else bearer
    return json.loads(_b64url(token.split(".")[1]))
