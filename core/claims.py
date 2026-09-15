"""The projection from token claims to the Cedar parties (iteration 6).

  no act claim:   principal = <type>::sub,      direct mode
  act claim:      principal = <type>::act.sub,  context.actingFor = <type>::sub

Role facts are the union of a `roles` claim on the actor and the
store's role facts for that actor: RFC 8693 puts identity claims in
the actor claim and says nothing about roles there, so a delegated
token may carry none. A role claim of any shape other than a list of
strings is an error.

claims_of decodes the bearer token the Gateway forwards. The Gateway's
JWT authorizer verified it; the trust rests on the gateway using that
authorizer, on passRequestHeaders forwarding the validated header, and
on the forwarded token being the inbound one.
"""

import base64
import json
from dataclasses import dataclass

ROLE_CLAIM = "roles"
PRINCIPAL_TYPE = "User"


class TokenError(Exception):
    """The forwarded header is not a bearer token this projection reads."""


@dataclass
class Projection:
    principal: str            # Cedar entity ref of the actor
    context: dict             # actingFor when delegated, else empty
    principal_entity: dict    # the actor with role parents
    mode: str                 # customer-direct, employee-direct, employee-for-customer


def _ref(sub: str) -> dict:
    return {"__entity": {"type": PRINCIPAL_TYPE, "id": sub}}


def _roles(claims: dict) -> set:
    roles = claims.get(ROLE_CLAIM, [])
    if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
        raise ValueError(f"{ROLE_CLAIM} claim is not a list of strings")
    return set(roles)


def stored_roles(entities: list, sub: str) -> set:
    for entity in entities:
        if entity["uid"] == {"type": PRINCIPAL_TYPE, "id": sub}:
            return {p["id"] for p in entity["parents"] if p["type"] == "Role"}
    return set()


def project(claims: dict, entities: list) -> Projection:
    """Claims of a decoded, verified token, plus the store, to the parties."""
    act = claims.get("act")
    if act is None:
        actor_sub = claims["sub"]
        roles = _roles(claims)
        context = {}
    else:
        actor_sub = act["sub"]
        roles = _roles(act)
        context = {"actingFor": _ref(claims["sub"])}
    roles = roles | stored_roles(entities, actor_sub)
    if act is None:
        mode = "employee-direct" if roles else "customer-direct"
    else:
        mode = "employee-for-customer"
    principal_entity = {
        "uid": {"type": PRINCIPAL_TYPE, "id": actor_sub},
        "attrs": {},
        "parents": [{"type": "Role", "id": role} for role in sorted(roles)],
    }
    return Projection(f'{PRINCIPAL_TYPE}::"{actor_sub}"', context, principal_entity, mode)


def _b64url(segment: str) -> bytes:
    standard = segment.translate(str.maketrans("-_", "+/")) + "=" * (-len(segment) % 4)
    return base64.b64decode(standard, validate=True)


def claims_of(bearer: str) -> dict:
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
