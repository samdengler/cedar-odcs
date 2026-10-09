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

from bearer import TokenError, claims_of, project
from enforce import ID_PATTERN, check_call, filter_object, filter_rows

log = logging.getLogger("cedar-odcs")

# MCP tool name to the verb, where the resource id comes from, and
# whether the tool carries a write payload or returns a list. Tool
# names follow the Gateway's convention, target name, three
# underscores, operation name.
TOOLS = {
    "orders___get_order":    {"action": "ReadOrder",   "id": "orderId", "returns": "object"},
    "orders___update_order": {"action": "UpdateOrder", "id": "orderId", "payload": "changes", "returns": "object"},
    "orders___cancel_order": {"action": "CancelOrder", "id": "orderId", "returns": "object"},
    "orders___refund_order": {"action": "RefundOrder", "id": "orderId", "returns": "object"},
    "orders___list_orders":  {"action": "ListOrders",  "collection": "orders", "returns": "list"},
}
# Every tool returns something, and the response leg filters every
# result; a tool without a declared result kind has its responses
# withheld. Write tools echo the order they changed, so they return an
# object like a read.

OUTPUT_VERSION = "1.0"


def _body(body):
    """The JSON-RPC body as a dict. The Gateway delivers it parsed; a
    string is parsed here rather than passed through unread."""
    if isinstance(body, str):
        body = json.loads(body)
    if not isinstance(body, dict):
        raise ValueError("request body is not a JSON object")
    return body


def _tool_call(body: dict):
    """(tool name, arguments) for a tools/call message, else None."""
    if body.get("method") != "tools/call":
        return None
    params = body.get("params") or {}
    arguments = params.get("arguments")
    return params.get("name"), arguments if isinstance(arguments, dict) else {}


def _header(headers: dict, name: str):
    """Header names are case-insensitive; the fixtures show one casing."""
    for key, value in (headers or {}).items():
        if key.lower() == name.lower():
            return value
    return None


def _resource(tool: dict, arguments: dict) -> str:
    if "collection" in tool:
        return f'Collection::"{tool["collection"]}"'
    order_id = arguments.get(tool["id"])
    if not isinstance(order_id, str) or not ID_PATTERN.match(order_id):
        raise ValueError(f"argument {tool['id']} is missing or not an id")
    return f'Order::"{order_id}"'


def _payload(tool: dict, arguments: dict):
    """The write payload for the payload round, or None for a tool
    that carries none. Every argument other than the resource id must
    be the declared payload: an argument the tool table does not name
    is rejected, so a write cannot arrive under another key and skip
    the field round."""
    expected = ({tool["id"]} if "id" in tool else set()) | ({tool["payload"]} if "payload" in tool else set())
    unexpected = set(arguments) - expected
    if unexpected:
        raise ValueError(f"unexpected arguments: {', '.join(sorted(unexpected))}")
    if "payload" not in tool:
        return None
    payload = arguments.get(tool["payload"])
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"argument {tool['payload']} must be an object naming the fields to change")
    return payload


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
    """REQUEST interception point: the verb round and the payload round.

    Anything the handler cannot evaluate is rejected: a malformed
    event, a header that is not a bearer token, an argument that is
    not an id. A raised exception would fail the invocation, and what
    the Gateway does with a failed interceptor is not something this
    handler should depend on.
    """
    try:
        request = event["mcp"]["gatewayRequest"]
        body = _body(request.get("body"))
        call = _tool_call(body)
        if call is None:
            return _pass_request(body)
        name, arguments = call
        tool = TOOLS.get(name)
        if tool is None:
            return _reject(body.get("id"), f"tool {name} is not governed; no policy covers it")
        claims = claims_of(_header(request.get("headers"), "Authorization"))
        decision = check_call(
            claims, f'Action::"{tool["action"]}"', _resource(tool, arguments), _payload(tool, arguments)
        )
    except (TokenError, ValueError, KeyError, TypeError) as e:
        log.info("rejected: request could not be evaluated: %s", e)
        return _reject(_request_id(event), f"request could not be evaluated: {e}")
    if decision.allowed:
        return _pass_request(body)
    if decision.denied_verb:
        message = f"{tool['action']} is not permitted for this caller"
    else:
        message = f"{tool['action']} rejected; fields not permitted: {', '.join(decision.denied_fields)}"
    log.info("rejected %s for %s: %s", name, project(claims).principal, message)
    return _reject(body.get("id"), message)


def _request_id(event: dict):
    try:
        return event["mcp"]["gatewayRequest"]["body"].get("id")
    except (KeyError, TypeError, AttributeError):
        return None


def _result_payload(result: dict):
    """The tool's JSON payload, from structuredContent or the text content."""
    if "structuredContent" in result:
        return result["structuredContent"]
    for item in result.get("content", []):
        if item.get("type") == "text":
            return json.loads(item["text"])
    return None


def _with_payload(result: dict, payload) -> dict:
    """The result with the filtered payload in structuredContent and in
    the text content. Content items that are not text are kept."""
    out = dict(result)
    if "structuredContent" in result:
        out["structuredContent"] = payload
    others = [item for item in result.get("content", []) if item.get("type") != "text"]
    out["content"] = [{"type": "text", "text": json.dumps(payload)}] + others
    return out


def response_handler(event: dict, context=None) -> dict:
    """RESPONSE interception point: rows dropped, fields stripped.

    A response the handler cannot filter is replaced by an error, so
    an unexpected payload leaves as nothing rather than as everything.
    """
    try:
        request = event["mcp"]["gatewayRequest"]
        response = event["mcp"]["gatewayResponse"]
        call = _tool_call(_body(request.get("body")))
        if call is None or "result" not in (response.get("body") or {}):
            return _pass_response(response)
        name, _ = call
        tool = TOOLS.get(name)
        if tool is None or "returns" not in tool:
            raise ValueError(f"tool {name} declares no result kind")
        claims = claims_of(_header(request.get("headers"), "Authorization"))
        result = response["body"]["result"]
        payload = _result_payload(result)
        if tool["returns"] == "list":
            if not isinstance(payload, list):
                raise ValueError("list tool returned no list")
            decision = filter_rows(claims, payload)
            filtered = decision.rows
        else:
            if not isinstance(payload, dict):
                raise ValueError("object tool returned no object")
            decision = filter_object(claims, payload)
            filtered = decision.rows[0] if decision.rows else {}
    except (TokenError, ValueError, KeyError, TypeError) as e:
        log.info("response withheld: could not be filtered: %s", e)
        return _reject(_request_id(event), f"response withheld; it could not be filtered: {e}")
    if decision.dropped or decision.stripped:
        log.info("filtered %s for %s: dropped %s, stripped %s",
                 name, project(claims).principal, decision.dropped, decision.stripped)
    body = dict(response["body"])
    body["result"] = _with_payload(result, filtered)
    return _pass_response({**response, "body": body})
