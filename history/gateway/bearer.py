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

Role membership is the union of a `roles` claim on the actor and the
role facts the store holds for that actor. The principal entity is
built per request with those roles as parents. A delegated token may
carry no roles at all, since the standard puts only identity claims
in the actor claim; the store then supplies them.

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
        roles = _roles(claims)
        context = {}
    else:
        actor_sub = act["sub"]
        roles = _roles(act)
        context = {"actingFor": _entity_ref(claims["sub"])}
    # Role facts are the union of what the token says and what the
    # store says. RFC 8693 puts identity claims in the actor claim and
    # says nothing about roles there, so a delegated token may carry
    # none; the store then supplies them. A role the token names that
    # the store does not is granted for this request.
    roles = roles | stored_roles(actor_sub)
    if act is None:
        mode = "employee-direct" if roles else "customer-direct"
    else:
        mode = "employee-for-customer"
    principal_entity = {
        "uid": {"type": "User", "id": actor_sub},
        "attrs": {},
        "parents": [{"type": "Role", "id": role} for role in sorted(roles)],
    }
    return Projection(_user(actor_sub), context, principal_entity, mode)


def _roles(claims: dict) -> set:
    """The role claim as a set of names; any other shape is an error,
    never a set of one-character roles."""
    roles = claims.get(ROLE_CLAIM, [])
    if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
        raise ValueError(f"{ROLE_CLAIM} claim is not a list of strings")
    return set(roles)


def stored_roles(sub: str) -> set:
    for entity in load_entities():
        if entity["uid"] == {"type": "User", "id": sub}:
            return {parent["id"] for parent in entity["parents"] if parent["type"] == "Role"}
    return set()


def load_policies() -> str:
    return (HERE / "policies.cedar").read_text()


def load_entities() -> list:
    return json.loads((HERE / "entities.json").read_text())


class TokenError(Exception):
    """The forwarded header is not a bearer token this handler reads."""


def _b64url(segment: str) -> bytes:
    # Strict decoding: a character outside the alphabet is an error,
    # never discarded.
    standard = segment.translate(str.maketrans("-_", "+/")) + "=" * (-len(segment) % 4)
    return base64.b64decode(standard, validate=True)


def claims_of(bearer: str) -> dict:
    """The payload of a JWT the Gateway has already verified.

    The interceptor sees the raw Authorization header and nothing
    parsed. The signature, issuer, audience, and expiry were checked
    by the Gateway's JWT authorizer before the interceptor ran, so the
    payload is decoded here without re-verifying. That trust rests on
    three conditions the deployment must meet: the gateway uses the
    JWT authorizer (an unauthenticated or IAM-authorized gateway
    forwards a header nobody checked); passRequestHeaders forwards the
    header the authorizer validated; and the token forwarded is the
    inbound one, whose sub and act claims the projection reads, and
    not a token the Gateway exchanged for the target. The handler
    reads the header from the request the Gateway forwarded and from
    nowhere else. Anything that is not a well-formed bearer JWT raises
    TokenError, which the handlers turn into a rejection.
    """
    if not isinstance(bearer, str) or not bearer.lower().startswith("bearer "):
        raise TokenError("no bearer token")
    parts = bearer.split(" ", 1)[1].strip().split(".")
    if len(parts) != 3:
        raise TokenError("not a JWT")
    try:
        claims = json.loads(_b64url(parts[1]))
    except (ValueError, UnicodeDecodeError) as e:
        raise TokenError(f"payload not decodable: {e}") from e
    if not isinstance(claims, dict) or "sub" not in claims:
        raise TokenError("no subject claim")
    return claims
