"""The claims mapping: which claims name the subject, the roles, and
the actor. The default mapping reads an identity the orders use case
already has; the Cognito mapping reads a claims dict shaped like a
Cognito access token."""

from cedar_odcs.engine.identities import ClaimsMapping, project
from usecases.orders.usecase import USE_CASE

COGNITO = ClaimsMapping(subject="username", roles="cognito:groups")


def test_the_default_mapping_reads_sub_and_roles():
    claims = {"iss": "https://issuer.example", "sub": "carol", "aud": "orders-gateway", "roles": ["support"]}
    p = project(claims, USE_CASE.entities)
    assert p.principal == 'User::"carol"'
    assert p.mode == "employee-direct"
    assert {"type": "Role", "id": "support"} in p.principal_entity["parents"]
    assert p.context == {}


def test_the_cognito_mapping_reads_username_and_groups():
    # A Cognito access token: sub is a UUID, the user is in username,
    # groups in cognito:groups, and client_id names the app client.
    # client_id differs from sub, so the actor is a User.
    claims = {
        "sub": "8f1c2a4e-5b6d-4e7f-9a0b-1c2d3e4f5a6b",
        "cognito:groups": ["support", "employee"],
        "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_EXAMPLE",
        "client_id": "3n4b5c6d7e8f9g0h1i2j3k4l5m",
        "origin_jti": "0c1d2e3f-4a5b-6c7d-8e9f-0a1b2c3d4e5f",
        "event_id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
        "token_use": "access",
        "scope": "aws.cognito.signin.user.admin",
        "auth_time": 1792300000,
        "exp": 1792303600,
        "iat": 1792300000,
        "jti": "2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e",
        "username": "carol",
    }
    p = project(claims, USE_CASE.entities, COGNITO)
    assert p.principal == 'User::"carol"'
    assert p.mode == "employee-direct"
    assert {p["id"] for p in p.principal_entity["parents"]} == {"support", "employee"}


def test_the_cognito_mapping_applies_inside_the_actor_claim():
    claims = {"sub": "a-uuid", "username": "alice", "client_id": "app",
              "act": {"sub": "c-uuid", "username": "carol", "cognito:groups": ["support"]}}
    p = project(claims, USE_CASE.entities, COGNITO)
    assert p.principal == 'User::"carol"'
    assert p.context == {"actingFor": {"__entity": {"type": "User", "id": "alice"}}}
    assert p.mode == "employee-for-customer"


def test_a_use_case_carries_the_default_mapping():
    assert USE_CASE.claims == ClaimsMapping()
