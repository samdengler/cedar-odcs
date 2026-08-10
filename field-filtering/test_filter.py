"""The response leg end to end: one upstream payload, filtered per caller.

The corpus (tests/field-filtering.json) pins the per-field decisions.
These tests pin the enforcement behavior on top of them: given a full
upstream response, each caller gets exactly the fields their granted
classification levels allow, and everything removed is reported.
"""

from field_filter import filter_response

# What the upstream API returns for order-1001: every field, including
# one (debugTrace) that appears in no data contract.
UPSTREAM_RESPONSE = {
    "id": "order-1001",
    "status": "shipped",
    "total": 129.99,
    "shippingAddress": "42 Elm St, Springfield",
    "cardLast4": "4242",
    "internalNotes": "customer called twice about delivery",
    "fraudScore": 0.02,
    "debugTrace": "cache-hit us-east-1",
}

ORDER = 'Order::"order-1001"'


def test_owner_gets_customer_visible_fields():
    result = filter_response('User::"alice"', ORDER, UPSTREAM_RESPONSE)
    assert set(result.body) == {"id", "status", "total", "shippingAddress", "cardLast4"}
    assert sorted(result.stripped) == ["debugTrace", "fraudScore", "internalNotes"]


def test_support_gets_public_and_internal_fields():
    result = filter_response('User::"carol"', ORDER, UPSTREAM_RESPONSE)
    assert set(result.body) == {"id", "status", "total", "internalNotes"}
    assert sorted(result.stripped) == [
        "cardLast4", "debugTrace", "fraudScore", "shippingAddress",
    ]


def test_non_owner_gets_nothing():
    # The object-level check would already have denied bob the order;
    # if a response reaches the field pass anyway, every field strips.
    result = filter_response('User::"bob"', ORDER, UPSTREAM_RESPONSE)
    assert result.body == {}
    assert sorted(result.stripped) == sorted(UPSTREAM_RESPONSE)


def test_values_pass_through_unchanged():
    result = filter_response('User::"alice"', ORDER, UPSTREAM_RESPONSE)
    for name, value in result.body.items():
        assert value == UPSTREAM_RESPONSE[name]
