"""The core handlers, driven by the Gateway's own event shapes (from iteration 10).

Every governance decision was pinned in an earlier iteration's corpus
and wrappers. These tests pin the last step: that the Gateway event
in, the Gateway result out, carries those decisions. A rejected call
comes back as a short-circuit response with a JSON-RPC error; a
filtered response comes back with rows dropped and fields stripped in
both the structured content and the text content.
"""

import json
from pathlib import Path

from cedar_osdc.gateway.handlers import handlers
from usecases.orders.usecase import TOOLS, USE_CASE

HERE = Path(__file__).parent
request_handler, response_handler = handlers(USE_CASE)


def event(name: str) -> dict:
    return json.loads((HERE / "events" / f"{name}.json").read_text())


def test_policies_and_entities_are_the_proven_ones():
    assert (HERE / "../policies.cedar").read_text() == (HERE / "../../../history/row-filtering/policies.cedar").read_text()
    assert json.loads((HERE / "../entities.json").read_text()) == json.loads((HERE / "../../../history/contract/entities.json").read_text())


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


def _mutated(name: str, mutate) -> dict:
    ev = event(name)
    mutate(ev)
    return ev


def test_update_without_its_payload_is_rejected():
    ev = _mutated("request-carol-updates-notes", lambda e: e["mcp"]["gatewayRequest"]["body"]["params"]["arguments"].pop("changes"))
    out = request_handler(ev)
    assert out["mcp"]["transformedGatewayResponse"]["statusCode"] == 403


def test_write_under_another_argument_name_is_rejected():
    def mutate(e):
        args = e["mcp"]["gatewayRequest"]["body"]["params"]["arguments"]
        args["patch"] = args.pop("changes")
    out = request_handler(_mutated("request-carol-updates-notes", mutate))
    message = out["mcp"]["transformedGatewayResponse"]["body"]["error"]["message"]
    assert "unexpected arguments: patch" in message


def test_missing_arguments_or_header_reject_rather_than_raise():
    ev = _mutated("request-alice-reads-own-order", lambda e: e["mcp"]["gatewayRequest"]["body"]["params"].pop("arguments"))
    assert request_handler(ev)["mcp"]["transformedGatewayResponse"]["statusCode"] == 403
    ev = _mutated("request-alice-reads-own-order", lambda e: e["mcp"]["gatewayRequest"]["headers"].pop("Authorization"))
    assert request_handler(ev)["mcp"]["transformedGatewayResponse"]["statusCode"] == 403
    ev = _mutated("request-alice-reads-own-order", lambda e: e["mcp"]["gatewayRequest"]["headers"].update({"Authorization": "Basic YWxpY2U6cHc="}))
    assert request_handler(ev)["mcp"]["transformedGatewayResponse"]["statusCode"] == 403


def test_header_name_casing_does_not_matter():
    def mutate(e):
        h = e["mcp"]["gatewayRequest"]["headers"]
        h["authorization"] = h.pop("Authorization")
    out = request_handler(_mutated("request-alice-reads-own-order", mutate))
    assert "transformedGatewayRequest" in out["mcp"]


def test_unfilterable_response_is_withheld():
    def mutate(e):
        e["mcp"]["gatewayResponse"]["body"]["result"] = {"content": [{"type": "image", "data": "...", "mimeType": "image/png"}]}
    out = response_handler(_mutated("response-alice-reads-own-order", mutate))
    assert out["mcp"]["transformedGatewayResponse"]["statusCode"] == 403
    assert "withheld" in out["mcp"]["transformedGatewayResponse"]["body"]["error"]["message"]


def test_non_text_content_items_are_kept():
    def mutate(e):
        e["mcp"]["gatewayResponse"]["body"]["result"]["content"].append({"type": "image", "data": "...", "mimeType": "image/png"})
    out = response_handler(_mutated("response-alice-reads-own-order", mutate))
    content = out["mcp"]["transformedGatewayResponse"]["body"]["result"]["content"]
    assert [c["type"] for c in content] == ["text", "image"]


# Both legs of one call, for every tool in the table. The request leg
# must pass and the response leg must filter; a tool the table names
# is covered end to end or the test fails.
BOTH_LEGS = {
    "orders___get_order": "response-alice-reads-own-order",
    "orders___update_order": "response-carol-updates-notes",
    "orders___cancel_order": "response-alice-cancels-own-order",
    "orders___refund_order": "response-dave-refunds",
    "orders___list_orders": "response-carol-for-alice-lists",
}


def test_every_tool_has_both_legs_covered():
    assert set(BOTH_LEGS) == set(TOOLS)


def test_both_legs_for_every_tool():
    for name, fixture in BOTH_LEGS.items():
        ev = event(fixture)
        assert "transformedGatewayRequest" in request_handler(ev)["mcp"], name
        out = response_handler(ev)["mcp"]["transformedGatewayResponse"]
        assert out["statusCode"] == 200, name
        payload = out["body"]["result"]["structuredContent"]
        rows = payload if isinstance(payload, list) else [payload]
        for row in rows:
            assert "fraudScore" not in row, name


def test_write_tools_echoing_the_order_are_filtered():
    # dave refunds and receives the order back: finance reads nothing of it.
    out = response_handler(event("response-dave-refunds"))["mcp"]["transformedGatewayResponse"]
    assert out["body"]["result"]["structuredContent"] == {}
    # carol's update echoes bob's order: support's fields only.
    out = response_handler(event("response-carol-updates-notes"))["mcp"]["transformedGatewayResponse"]
    assert "shippingAddress" not in out["body"]["result"]["structuredContent"]
    assert "internalNotes" in out["body"]["result"]["structuredContent"]


def test_nested_write_payload_is_examined_leaf_by_leaf():
    def mutate(e):
        e["mcp"]["gatewayRequest"]["body"]["params"]["arguments"]["changes"] = {
            "shippingAddress": {"street": "2 Oak Ln", "isAdmin": True}
        }
    out = request_handler(_mutated("request-carol-for-alice-updates-address-and-total", mutate))
    message = out["mcp"]["transformedGatewayResponse"]["body"]["error"]["message"]
    assert "shippingAddress.street" in message and "shippingAddress.isAdmin" in message


def test_nested_response_values_are_examined_leaf_by_leaf():
    def mutate(e):
        payload = e["mcp"]["gatewayResponse"]["body"]["result"]["structuredContent"]
        payload["shippingAddress"] = {"street": "1 Oak Ln", "fraudScore": 0.9}
        payload["lines"] = [{"sku": "a", "internalNotes": "x"}]
        e["mcp"]["gatewayResponse"]["body"]["result"]["content"][0]["text"] = json.dumps(payload)
    out = response_handler(_mutated("response-alice-reads-own-order", mutate))
    payload = out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"]
    assert "shippingAddress" not in payload and "lines" not in payload


def test_string_body_is_parsed_not_passed():
    ev = _mutated("request-alice-refunds-own-order", lambda e: e["mcp"]["gatewayRequest"].update({"body": json.dumps(e["mcp"]["gatewayRequest"]["body"])}))
    out = request_handler(ev)
    assert out["mcp"]["transformedGatewayResponse"]["statusCode"] == 403
    assert "RefundOrder is not permitted" in out["mcp"]["transformedGatewayResponse"]["body"]["error"]["message"]
