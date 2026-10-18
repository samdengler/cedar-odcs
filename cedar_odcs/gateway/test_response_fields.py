"""The live Gateway's response event carries path, httpMethod, and
isStreamingResponse beside statusCode, headers, and body (observed on
the applied-odcs deployment, October 2026).  A transformed response
that echoes those back is rejected as an invalid interceptor response,
so the handlers return only the three documented fields."""

import json
from pathlib import Path

from cedar_odcs.gateway.handlers import handlers
from usecases.orders.usecase import USE_CASE

EVENTS = Path(__file__).resolve().parents[2] / "usecases/orders/tests/events"
request_handler, response_handler = handlers(USE_CASE)


def live_shaped(name: str) -> dict:
    event = json.loads((EVENTS / f"{name}.json").read_text())
    event["mcp"]["gatewayRequest"]["context"] = None
    response = event["mcp"]["gatewayResponse"]
    event["mcp"]["gatewayResponse"] = {"path": "/mcp", "httpMethod": "POST", "headers": {},
                                       **{k: v for k, v in response.items() if k != "headers"},
                                       "isStreamingResponse": False}
    return event


def test_a_filtered_response_carries_only_the_documented_fields():
    out = response_handler(live_shaped("response-alice-reads-own-order"))
    assert set(out["mcp"]["transformedGatewayResponse"]) == {"statusCode", "body"}


def test_a_passed_through_response_carries_only_the_documented_fields():
    event = live_shaped("response-alice-reads-own-order")
    event["mcp"]["gatewayRequest"]["body"] = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    event["mcp"]["gatewayResponse"]["body"] = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18"}}
    out = response_handler(event)["mcp"]["transformedGatewayResponse"]
    assert set(out) == {"statusCode", "body"}


def test_a_notification_response_has_no_body_to_carry():
    event = live_shaped("response-alice-reads-own-order")
    event["mcp"]["gatewayRequest"]["body"] = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    response = event["mcp"]["gatewayResponse"]
    del response["body"]
    response["statusCode"] = 202
    assert response_handler(event)["mcp"]["transformedGatewayResponse"] == {"statusCode": 202}
