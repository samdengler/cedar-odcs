"""The projection from token claims to the Cedar parties (iteration 6).

  no act claim:   principal = <type>::sub,      direct mode
  act claim:      principal = <type>::act.sub,  context.actingFor = <type>::sub

Role facts are the union of a `roles` claim on the actor and the
store's role facts for that actor: RFC 8693 puts identity claims in
the actor claim and says nothing about roles there, so a delegated
token may carry none. A role claim of any shape other than a list of
strings is an error.

Decoding the bearer token itself (claims_of, TokenError) is a Gateway
concern and lives in cedar_osdc.gateway.handlers; this module takes
already-decoded claims.
"""

from dataclasses import dataclass

ROLE_CLAIM = "roles"
PRINCIPAL_TYPE = "User"
# A workload token names no human: its subject is the client id it was
# issued to. Assumed claim shape, to confirm against a real token: the
# token carries client_id and sub equals it. Such an actor is typed
# Agent; a human actor is a User.
WORKLOAD_CLAIM = "client_id"
AGENT_TYPE = "Agent"


@dataclass
class Projection:
    principal: str            # Cedar entity ref of the actor
    context: dict             # actingFor when delegated, else empty
    principal_entity: dict    # the actor with role parents
    mode: str                 # customer-direct, employee-direct, employee-for-customer
    acted_for_entity: dict = None  # the human acted for, with role parents


def _ref(sub: str) -> dict:
    return {"__entity": {"type": PRINCIPAL_TYPE, "id": sub}}


def _actor_type(claims: dict) -> str:
    if claims.get(WORKLOAD_CLAIM) is not None and claims.get(WORKLOAD_CLAIM) == claims.get("sub"):
        return AGENT_TYPE
    return PRINCIPAL_TYPE


def _roles(claims: dict) -> set:
    roles = claims.get(ROLE_CLAIM, [])
    if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
        raise ValueError(f"{ROLE_CLAIM} claim is not a list of strings")
    return set(roles)


def stored_roles(entities: list, entity_type: str, sub: str) -> set:
    for entity in entities:
        if entity["uid"] == {"type": entity_type, "id": sub}:
            return {p["id"] for p in entity["parents"] if p["type"] == "Role"}
    return set()


def _entity(entity_type: str, sub: str, roles: set) -> dict:
    return {
        "uid": {"type": entity_type, "id": sub},
        "attrs": {},
        "parents": [{"type": "Role", "id": role} for role in sorted(roles)],
    }


def project(claims: dict, entities: list) -> Projection:
    """Claims of a decoded, verified token, plus the store, to the parties.

    With an exchanged token the actor is the agent and the human is
    the subject: the agent becomes the principal, typed Agent, and the
    human becomes context.actingFor with the roles the token's own
    role claim and the store give them. A human calling without the
    agent is the principal, a User.
    """
    act = claims.get("act")
    acted_for = None
    if act is None:
        actor_sub = claims["sub"]
        actor_type = _actor_type(claims)
        roles = _roles(claims) | stored_roles(entities, actor_type, actor_sub)
        context = {}
        if actor_type == AGENT_TYPE:
            mode = "customer-conversation"
        else:
            mode = "employee-direct" if roles else "customer-direct"
    else:
        actor_sub = act["sub"]
        actor_type = _actor_type(act)
        roles = _roles(act) | stored_roles(entities, actor_type, actor_sub)
        human = claims["sub"]
        human_roles = _roles(claims) | stored_roles(entities, PRINCIPAL_TYPE, human)
        acted_for = _entity(PRINCIPAL_TYPE, human, human_roles)
        context = {"actingFor": _ref(human)}
        mode = "employee-for-customer"
    principal_entity = _entity(actor_type, actor_sub, roles)
    return Projection(f'{actor_type}::"{actor_sub}"', context, principal_entity, mode, acted_for)
