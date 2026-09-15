"""The handlers, driven by the Gateway's own event shapes.

Every governance decision was pinned in an earlier iteration's corpus
and wrappers. These tests pin the last step: that the Gateway event
in, the Gateway result out, carries those decisions. A rejected call
comes back as a short-circuit response with a JSON-RPC error; a
filtered response comes back with rows dropped and fields stripped in
both the structured content and the text content.
"""

import json
from pathlib import Path

from interceptor import request_handler, response_handler

HERE = Path(__file__).parent


def event(name: str) -> dict:
    return json.loads((HERE / "events" / f"{name}.json").read_text())


def test_policies_and_entities_are_the_proven_ones():
    assert (HERE / "policies.cedar").read_text() == (HERE / "../row-filtering/policies.cedar").read_text()
    assert (HERE / "entities.json").read_text() == (HERE / "../contract/entities.json").read_text()


def test_allowed_read_passes_the_request_through():
    out = request_handler(event("request-alice-reads-own-order"))
    assert out["interceptorOutputVersion"] == "1.0"
    assert "transformedGatewayResponse" not in out["mcp"]
    assert out["mcp"]["transformedGatewayRequest"]["body"]["params"]["name"] == "orders___get_order"


def test_verb_not_held_short_circuits_with_a_json_rpc_error():
    out = request_handler(event("request-alice-refunds-own-order"))
    response = out["mcp"]["transformedGatewayResponse"]
    assert response["statusCode"] == 403
    assert response["body"]["id"] == 2
    assert "RefundOrder is not permitted" in response["body"]["error"]["message"]


def test_finance_refund_passes():
    out = request_handler(event("request-dave-refunds"))
    assert "transformedGatewayRequest" in out["mcp"]


def test_role_granted_update_passes_the_payload_round():
    out = request_handler(event("request-carol-updates-notes"))
    assert "transformedGatewayRequest" in out["mcp"]


def test_denied_field_rejects_the_call_and_names_the_field():
    out = request_handler(event("request-carol-for-alice-updates-address-and-total"))
    message = out["mcp"]["transformedGatewayResponse"]["body"]["error"]["message"]
    assert "fields not permitted: total" in message


def test_ungoverned_tool_is_rejected():
    out = request_handler(event("request-ungoverned-tool"))
    assert out["mcp"]["transformedGatewayResponse"]["statusCode"] == 403


def test_other_methods_pass_through():
    out = request_handler(event("request-tools-list"))
    assert out["mcp"]["transformedGatewayRequest"]["body"]["method"] == "tools/list"


def test_owner_response_is_stripped_to_customer_fields():
    out = response_handler(event("response-alice-reads-own-order"))
    result = out["mcp"]["transformedGatewayResponse"]["body"]["result"]
    assert set(result["structuredContent"]) == {"id", "owner", "status", "total", "shippingAddress", "cardLast4", "estimatedDelivery"}
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]


def test_support_response_is_stripped_to_support_fields():
    out = response_handler(event("response-carol-reads-order"))
    payload = out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"]
    assert "internalNotes" in payload
    assert "shippingAddress" not in payload and "cardLast4" not in payload


def test_list_while_acting_returns_the_customers_rows():
    out = response_handler(event("response-carol-for-alice-lists"))
    rows = out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"]
    assert [r["id"] for r in rows] == ["order-1001", "order-3003"]
    assert "shippingAddress" in rows[0] and "internalNotes" not in rows[0]


def test_finance_list_is_empty():
    out = response_handler(event("response-dave-lists"))
    assert out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"] == []


def test_response_headers_and_status_are_kept():
    out = response_handler(event("response-alice-reads-own-order"))
    response = out["mcp"]["transformedGatewayResponse"]
    assert response["statusCode"] == 200
    assert response["headers"] == {"Mcp-Session-Id": "session-1"}
