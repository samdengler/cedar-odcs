"""The request leg end to end: write payloads accepted or rejected whole.

The corpus (tests/field-writes.json) pins the per-field decisions.
These tests pin the enforcement on top of them: a payload with any
denied field is rejected as a unit, and the rejection names the
denied fields.
"""

from write_gate import check_request

ORDER = 'Order::"order-1001"'


def test_owner_updates_shipping_address():
    result = check_request('User::"alice"', ORDER, {"shippingAddress": "1 Oak Ln"})
    assert result.allowed
    assert result.denied_fields == []


def test_one_denied_field_rejects_the_whole_call():
    result = check_request(
        'User::"alice"', ORDER, {"shippingAddress": "1 Oak Ln", "total": 0.99}
    )
    assert not result.allowed
    assert result.denied_fields == ["total"]


def test_mass_assignment_field_rejects_the_call():
    result = check_request(
        'User::"alice"', ORDER, {"shippingAddress": "1 Oak Ln", "isAdmin": True}
    )
    assert not result.allowed
    assert result.denied_fields == ["isAdmin"]


def test_support_writes_nothing():
    result = check_request('User::"carol"', ORDER, {"shippingAddress": "1 Oak Ln"})
    assert not result.allowed
    assert result.denied_fields == ["shippingAddress"]


def test_non_owner_writes_nothing():
    result = check_request('User::"bob"', ORDER, {"shippingAddress": "1 Oak Ln"})
    assert not result.allowed
    assert result.denied_fields == ["shippingAddress"]


def test_an_empty_payload_is_rejected():
    result = check_request('User::"alice"', ORDER, {})
    assert not result.allowed
    assert result.denied_fields == ["<no payload>"]
