"""AgentCore Gateway interceptors: the request leg and the response leg.

Two Lambda handlers, one per interception point, in the event and
result formats the Gateway documents for MCP targets. The Gateway
invokes the request interceptor before it calls the target and the
response interceptor before it answers the agent; each receives the
JSON-RPC message in flight and returns a transformed one, or, on the
request leg, a response that short-circuits the call.

The handlers do three things and delegate the rest to enforce.py:
decode the bearer token the Gateway forwarded (passRequestHeaders
must be on), map the MCP tool name to a verb and a resource, and
turn the decision into the Gateway's output format. A rejected call
never reaches the upstream API; a response leaves with rows dropped
and fields stripped, and the removals in the log.

events/*.json are the exact event shapes, hand-written from the
documentation, that test_interceptor.py drives the handlers with.
"""

import json
import logging

from claims import claims_of, project
from enforce import check_call, filter_object, filter_rows

log = logging.getLogger("cedar-osdc")

# MCP tool name to the verb, where the resource id comes from, and
# whether the tool carries a write payload or returns a list. Tool
# names follow the Gateway's convention, target name, three
# underscores, operation name.
TOOLS = {
    "orders___get_order":    {"action": "ReadOrder",   "id": "orderId", "returns": "object"},
    "orders___update_order": {"action": "UpdateOrder", "id": "orderId", "payload": "changes"},
    "orders___cancel_order": {"action": "CancelOrder", "id": "orderId"},
    "orders___refund_order": {"action": "RefundOrder", "id": "orderId"},
    "orders___list_orders":  {"action": "ListOrders",  "collection": "orders", "returns": "list"},
}

OUTPUT_VERSION = "1.0"


def _tool_call(body: dict):
    """(tool name, arguments) for a tools/call message, else None."""
    if body.get("method") != "tools/call":
        return None
    params = body.get("params", {})
    return params.get("name"), params.get("arguments", {})


def _resource(tool: dict, arguments: dict) -> str:
    if "collection" in tool:
        return f'Collection::"{tool["collection"]}"'
    return f'Order::"{arguments[tool["id"]]}"'


def _reject(request_id, message: str) -> dict:
    """A JSON-RPC error the Gateway returns instead of calling the target."""
    return {
        "interceptorOutputVersion": OUTPUT_VERSION,
        "mcp": {
            "transformedGatewayResponse": {
                "statusCode": 403,
                "body": {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": message},
                },
            }
        },
    }


def _pass_request(body: dict) -> dict:
    return {
        "interceptorOutputVersion": OUTPUT_VERSION,
        "mcp": {"transformedGatewayRequest": {"body": body}},
    }


def _pass_response(response: dict) -> dict:
    return {
        "interceptorOutputVersion": OUTPUT_VERSION,
        "mcp": {"transformedGatewayResponse": response},
    }


def request_handler(event: dict, context=None) -> dict:
    """REQUEST interception point: the verb round and the payload round."""
    request = event["mcp"]["gatewayRequest"]
    body = request["body"]
    call = _tool_call(body)
    if call is None:
        return _pass_request(body)
    name, arguments = call
    tool = TOOLS.get(name)
    if tool is None:
        return _reject(body.get("id"), f"tool {name} is not governed; no policy covers it")
    claims = claims_of(request["headers"]["Authorization"])
    payload = arguments.get(tool["payload"]) if "payload" in tool else None
    decision = check_call(claims, f'Action::"{tool["action"]}"', _resource(tool, arguments), payload)
    if decision.allowed:
        return _pass_request(body)
    if decision.denied_verb:
        message = f"{tool['action']} is not permitted for this caller"
    else:
        message = f"{tool['action']} rejected; fields not permitted: {', '.join(decision.denied_fields)}"
    log.info("rejected %s for %s: %s", name, project(claims).principal, message)
    return _reject(body.get("id"), message)


def _result_payload(result: dict):
    """The tool's JSON payload, from structuredContent or the text content."""
    if "structuredContent" in result:
        return result["structuredContent"]
    for item in result.get("content", []):
        if item.get("type") == "text":
            return json.loads(item["text"])
    return None


def _with_payload(result: dict, payload) -> dict:
    out = dict(result)
    if "structuredContent" in result:
        out["structuredContent"] = payload
    out["content"] = [{"type": "text", "text": json.dumps(payload)}]
    return out


def response_handler(event: dict, context=None) -> dict:
    """RESPONSE interception point: rows dropped, fields stripped."""
    request = event["mcp"]["gatewayRequest"]
    response = event["mcp"]["gatewayResponse"]
    call = _tool_call(request["body"])
    if call is None or "result" not in response.get("body", {}):
        return _pass_response(response)
    name, _ = call
    tool = TOOLS.get(name)
    if tool is None or "returns" not in tool:
        return _pass_response(response)
    claims = claims_of(request["headers"]["Authorization"])
    result = response["body"]["result"]
    payload = _result_payload(result)
    if tool["returns"] == "list":
        decision = filter_rows(claims, payload)
        filtered = decision.rows
    else:
        decision = filter_object(claims, payload)
        filtered = decision.rows[0] if decision.rows else {}
    if decision.dropped or decision.stripped:
        log.info("filtered %s for %s: dropped %s, stripped %s",
                 name, project(claims).principal, decision.dropped, decision.stripped)
    body = dict(response["body"])
    body["result"] = _with_payload(result, filtered)
    return _pass_response({**response, "body": body})
