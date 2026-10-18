"""An MCP server target's results, from the live Gateway (applied-odcs,
AppliedOdcsRuntime, October 2026): the orders tools as a FastMCP server on
AgentCore Runtime.  The event envelope is the Lambda function target's;
the result is not.  A list tool's rows arrive in structuredContent as
{"result": [...]}, with one text item per row, and a single record arrives
in structuredContent as the object.  The decisions must be the ones the
same rows get from a Lambda function target, whose result is one text item
and no structuredContent."""

import copy
import dataclasses
import json
from pathlib import Path

from cedar_odcs.engine.identities import ClaimsMapping
from cedar_odcs.gateway.handlers import handlers
from usecases.orders.usecase import USE_CASE

# Beside events/, not in it: the agreement test replays events/ with the
# use case's own claims mapping, and these carry Cognito tokens.
EVENTS = Path(__file__).resolve().parents[2] / "usecases/orders/tests/mcp-server-events"
# The live tokens are Cognito access tokens.
COGNITO = dataclasses.replace(USE_CASE, claims=ClaimsMapping(subject="username", roles="cognito:groups"))
_, response_handler = handlers(COGNITO)


def event(name: str) -> dict:
    return json.loads((EVENTS / f"runtime-response-{name}.json").read_text())


def as_lambda_target(mcp_event: dict) -> dict:
    """The same event with the result a Lambda function target sends."""
    out = copy.deepcopy(mcp_event)
    result = out["mcp"]["gatewayResponse"]["body"]["result"]
    content = result["structuredContent"]
    rows = content["result"] if set(content) == {"result"} else content
    out["mcp"]["gatewayResponse"]["body"]["result"] = {
        "isError": False, "content": [{"type": "text", "text": json.dumps(rows)}]}
    return out


def transformed(e: dict) -> dict:
    return response_handler(e, None)["mcp"]["transformedGatewayResponse"]


def test_the_live_list_result_is_wrapped():
    result = event("carol-lists")["mcp"]["gatewayResponse"]["body"]["result"]
    assert set(result["structuredContent"]) == {"result"}
    assert len(result["content"]) == len(result["structuredContent"]["result"]) == 5


def test_a_wrapped_list_is_filtered_and_leaves_wrapped():
    out = transformed(event("carol-lists"))
    result = out["body"]["result"]
    rows = result["structuredContent"]["result"]
    assert set(result["structuredContent"]) == {"result"}
    assert [item["type"] for item in result["content"]] == ["text"]
    assert json.loads(result["content"][0]["text"]) == rows
    assert len(rows) == 5
    assert all(set(row) == {"id", "owner", "status", "total", "internalNotes", "estimatedDelivery"} for row in rows)


def test_a_wrapped_list_gets_the_lambda_target_decision():
    mcp = event("carol-lists")
    from_mcp = transformed(mcp)["body"]["result"]["structuredContent"]["result"]
    from_lambda = json.loads(transformed(as_lambda_target(mcp))["body"]["result"]["content"][0]["text"])
    assert from_mcp == from_lambda


def test_a_single_record_gets_the_lambda_target_decision():
    mcp = event("alice-updates-address")
    out = transformed(mcp)["body"]["result"]
    from_lambda = json.loads(transformed(as_lambda_target(mcp))["body"]["result"]["content"][0]["text"])
    assert out["structuredContent"] == from_lambda == json.loads(out["content"][0]["text"])
    assert out["structuredContent"]["owner"] == "alice"


def test_a_list_tool_with_more_than_a_result_key_is_still_withheld():
    e = event("carol-lists")
    e["mcp"]["gatewayResponse"]["body"]["result"]["structuredContent"]["next"] = "page-2"
    out = transformed(e)
    assert out["statusCode"] == 403
    assert "list tool returned no list" in out["body"]["error"]["message"]


def test_an_object_tool_with_a_result_key_is_not_unwrapped():
    e = event("alice-updates-address")
    result = e["mcp"]["gatewayResponse"]["body"]["result"]
    result["structuredContent"] = {"result": [result["structuredContent"]]}
    # The engine reads {"result": [...]} as the record, which names no
    # order the caller may read, so nothing of it is shown.
    assert transformed(e)["body"]["result"]["structuredContent"] == {}
