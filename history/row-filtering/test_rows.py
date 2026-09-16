"""The response leg for a list, end to end.

The corpus (tests/row-filtering.json) pins that the list verb is
allowed. These tests pin what the wrapper does with the response:
which rows survive for each caller and mode, that surviving rows are
field-filtered, and that rows the wrapper cannot place fail closed.
"""

from row_filter import filter_rows

ACTING_FOR_ALICE = {"actingFor": {"__entity": {"type": "User", "id": "alice"}}}


def upstream_rows():
    """What the orders API returns to its service credential: everything."""
    return [
        {"id": "order-1001", "owner": "alice", "status": "shipped", "total": 120.0,
         "shippingAddress": "1 Oak Ln", "cardLast4": "4242", "internalNotes": "called back",
         "fraudScore": 0.02, "estimatedDelivery": "2026-09-20"},
        {"id": "order-2002", "owner": "bob", "status": "processing", "total": 45.5,
         "shippingAddress": "9 Elm St", "cardLast4": "1111", "internalNotes": "",
         "fraudScore": 0.40, "estimatedDelivery": "2026-09-22"},
        {"id": "order-3003", "owner": "alice", "status": "processing", "total": 8.0,
         "shippingAddress": "1 Oak Ln", "cardLast4": "4242", "internalNotes": "gift",
         "fraudScore": 0.01, "estimatedDelivery": "2026-09-25"},
    ]


def test_customer_sees_own_rows_with_customer_fields():
    result = filter_rows('User::"alice"', upstream_rows())
    assert [r["id"] for r in result.rows] == ["order-1001", "order-3003"]
    assert result.dropped == [{"position": 1, "id": "order-2002", "reason": "ReadOrder denied"}]
    assert set(result.rows[0]) == {"id", "owner", "status", "total", "shippingAddress", "cardLast4", "estimatedDelivery"}
    assert result.stripped == {0: ["internalNotes", "fraudScore"], 2: ["internalNotes", "fraudScore"]}


def test_support_sees_every_row_with_support_fields():
    result = filter_rows('User::"carol"', upstream_rows())
    assert [r["id"] for r in result.rows] == ["order-1001", "order-2002", "order-3003"]
    assert result.dropped == []
    assert set(result.rows[1]) == {"id", "owner", "status", "total", "internalNotes", "estimatedDelivery"}
    assert result.stripped[1] == ["shippingAddress", "cardLast4", "fraudScore"]


def test_finance_sees_no_rows():
    result = filter_rows('User::"dave"', upstream_rows())
    assert result.rows == []
    assert [d["id"] for d in result.dropped] == ["order-1001", "order-2002", "order-3003"]


def test_acting_for_a_customer_sees_the_customers_rows_with_customer_fields():
    result = filter_rows('User::"carol"', upstream_rows(), ACTING_FOR_ALICE)
    assert [r["id"] for r in result.rows] == ["order-1001", "order-3003"]
    assert "shippingAddress" in result.rows[0]
    assert "internalNotes" not in result.rows[0]


def test_rows_come_from_the_payload_not_the_store():
    # order-3003 exists in no entities.json; alice owns it because the row says so.
    rows = [{"id": "order-3003", "owner": "alice", "status": "processing"}]
    assert filter_rows('User::"alice"', rows).rows == rows
    assert filter_rows('User::"bob"', rows).rows == []


def test_a_row_without_an_owner_is_decided_without_ownership():
    rows = [{"id": "order-4004", "status": "processing", "internalNotes": "x"}]
    # A customer reaches it only through ownership, which errors: dropped.
    result = filter_rows('User::"alice"', rows)
    assert result.rows == []
    assert result.dropped == [{"position": 0, "id": "order-4004", "reason": "ReadOrder denied"}]
    # Support reads any order and needs no owner: kept, with support's fields.
    result = filter_rows('User::"carol"', rows)
    assert result.rows == [{"id": "order-4004", "status": "processing", "internalNotes": "x"}]


def test_a_row_without_a_usable_id_is_dropped():
    for row in [{"owner": "alice"}, {"id": 7, "owner": "alice"}, {"id": 'order"1', "owner": "alice"}]:
        result = filter_rows('User::"alice"', [row])
        assert result.rows == []
        assert result.dropped == [{"position": 0, "id": None, "reason": "no usable id"}]
