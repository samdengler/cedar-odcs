"""The three modes, each entered through a token payload.

The corpus (tests/on-behalf-of.json) pins decisions for requests with
an explicit principal and context. These tests pin the projection in
front of it: the same decisions reached from the claims of a decoded
token, so a real token can be checked against the mode it should land
in.
"""

import json
from pathlib import Path

from claims import is_allowed, project

TOKENS = Path(__file__).parent / "tokens"
ALICE_ORDER = 'Order::"order-1001"'
BOB_ORDER = 'Order::"order-2002"'


def token(name: str) -> dict:
    return json.loads((TOKENS / f"{name}.json").read_text())


def test_customer_direct_projection():
    p = project(token("customer-direct"))
    assert p.mode == "customer-direct"
    assert p.principal == 'User::"alice"'
    assert p.context == {}
    assert p.principal_entity["parents"] == []


def test_employee_direct_projection():
    p = project(token("employee-direct"))
    assert p.mode == "employee-direct"
    assert p.principal == 'User::"carol"'
    assert p.context == {}
    assert p.principal_entity["parents"] == [{"type": "Role", "id": "support"}]


def test_employee_for_customer_projection():
    p = project(token("employee-for-customer"))
    assert p.mode == "employee-for-customer"
    assert p.principal == 'User::"carol"'
    assert p.context == {"actingFor": {"__entity": {"type": "User", "id": "alice"}}}
    assert p.principal_entity["parents"] == [{"type": "Role", "id": "support"}]


def test_customer_direct_reads_own_order_only():
    assert is_allowed(token("customer-direct"), 'Action::"ReadOrder"', ALICE_ORDER).allowed
    assert not is_allowed(token("customer-direct"), 'Action::"ReadOrder"', BOB_ORDER).allowed


def test_employee_direct_reads_any_order_and_internal_fields():
    t = token("employee-direct")
    assert is_allowed(t, 'Action::"ReadOrder"', BOB_ORDER).allowed
    assert is_allowed(t, 'Action::"ReadOrderField"', BOB_ORDER, {"field": "internalNotes"}).allowed
    assert not is_allowed(t, 'Action::"ReadOrderField"', BOB_ORDER, {"field": "shippingAddress"}).allowed


def test_employee_for_customer_holds_the_customers_access():
    t = token("employee-for-customer")
    assert is_allowed(t, 'Action::"ReadOrder"', ALICE_ORDER).allowed
    assert not is_allowed(t, 'Action::"ReadOrder"', BOB_ORDER).allowed
    assert is_allowed(t, 'Action::"ReadOrderField"', ALICE_ORDER, {"field": "shippingAddress"}).allowed
    assert not is_allowed(t, 'Action::"ReadOrderField"', ALICE_ORDER, {"field": "internalNotes"}).allowed


def test_roles_are_the_union_of_token_and_store():
    # The store says carol is support; a delegated token whose actor
    # claim carries no roles, as RFC 8693 allows, still lands carol in
    # the acting mode with the store's roles.
    bare = {**token("employee-for-customer"), "act": {"sub": "carol"}}
    assert project(bare).principal_entity["parents"] == [{"type": "Role", "id": "support"}]
    assert is_allowed(bare, 'Action::"ReadOrder"', ALICE_ORDER).allowed
    # A role the token names and the store does not is granted.
    promoted = {**token("customer-direct"), "sub": "bob", "roles": ["support"]}
    assert is_allowed(promoted, 'Action::"ReadOrder"', ALICE_ORDER).allowed


def test_a_malformed_role_claim_is_an_error():
    import pytest
    with pytest.raises(ValueError):
        project({**token("employee-direct"), "roles": "support"})


def test_customer_token_with_an_actor_claim_is_forbidden():
    forged = {**token("customer-direct"), "sub": "alice", "act": {"sub": "bob", "roles": []}}
    result = is_allowed(forged, 'Action::"ReadOrder"', ALICE_ORDER)
    assert not result.allowed
    assert result.determining_policies == ["policy11"]
