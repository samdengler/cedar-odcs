"""The request leg end to end: verbs held by roles, then payload fields.

The corpus (tests/function-level.json) pins the per-request decisions.
These tests pin the enforcement built on them: a verb the caller's
role does not hold rejects the call before the payload is looked at,
and a role-granted update is bounded by the writers map.
"""

from request_gate import check_call

OWN = 'Order::"order-1001"'
OTHER = 'Order::"order-2002"'


def test_finance_refunds():
    result = check_call('User::"dave"', 'Action::"RefundOrder"', OWN)
    assert result.allowed


def test_owner_may_not_refund_own_order():
    result = check_call('User::"alice"', 'Action::"RefundOrder"', OWN)
    assert not result.allowed
    assert result.denied_verb
    assert result.denied_fields == []


def test_customer_may_not_cancel_another_order():
    result = check_call('User::"alice"', 'Action::"CancelOrder"', OTHER)
    assert not result.allowed
    assert result.denied_verb


def test_support_updates_internal_notes_on_any_order():
    result = check_call(
        'User::"carol"', 'Action::"UpdateOrder"', OTHER, {"internalNotes": "called back"}
    )
    assert result.allowed
    assert result.denied_fields == []


def test_support_update_is_bounded_by_the_writers_map():
    result = check_call(
        'User::"carol"',
        'Action::"UpdateOrder"',
        OTHER,
        {"internalNotes": "called back", "shippingAddress": "1 Oak Ln"},
    )
    assert not result.allowed
    assert not result.denied_verb
    assert result.denied_fields == ["shippingAddress"]


def test_denied_verb_short_circuits_the_payload_round():
    # bob holds no verb on alice's order; the payload is never examined.
    result = check_call(
        'User::"bob"', 'Action::"UpdateOrder"', OWN, {"shippingAddress": "1 Oak Ln"}
    )
    assert not result.allowed
    assert result.denied_verb
    assert result.denied_fields == []


def test_a_role_granted_update_with_no_payload_is_rejected():
    result = check_call('User::"carol"', 'Action::"UpdateOrder"', OTHER, {})
    assert not result.allowed
    assert not result.denied_verb
    assert result.denied_fields == ["<no payload>"]
