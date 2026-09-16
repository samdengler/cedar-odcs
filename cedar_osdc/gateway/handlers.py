"""AgentCore Gateway interceptor handlers, for any use case.

handlers(use_case) returns (request_handler, response_handler) in the
event and result formats the Gateway documents for MCP targets. A
handler reads the event, hands the engine a Call (engine/calls.py
maps the tool table onto the engine's terms) and writes the engine's
decision back as a Gateway result.

Anything a handler cannot evaluate is rejected or withheld.

Decoding the bearer token the Gateway forwards (claims_of, TokenError)
lives here too: it is a Gateway concern, not the engine's. The
Gateway's JWT authorizer verified the token; the trust rests on the
gateway using that authorizer, on passRequestHeaders forwarding the
validated header, and on the forwarded token being the inbound one.
"""

import base64
import json
import logging

from cedar_osdc.engine import calls
from cedar_osdc.engine.enforce import Engine
from cedar_osdc.engine.usecase import UseCase

log = logging.getLogger("cedar-osdc")
OUTPUT_VERSION = "1.0"


class TokenError(Exception):
    """The forwarded header is not a bearer token this decoding reads."""


def _b64url(segment: str) -> bytes:
    standard = segment.translate(str.maketrans("-_", "+/")) + "=" * (-len(segment) % 4)
    return base64.b64decode(standard, validate=True)


def claims_of(bearer: str) -> dict:
    if not isinstance(bearer, str) or not bearer.lower().startswith("bearer "):
        raise TokenError("no bearer token")
    parts = bearer.split(" ", 1)[1].strip().split(".")
    if len(parts) != 3:
        raise TokenError("not a JWT")
    try:
        claims = json.loads(_b64url(parts[1]))
    except (ValueError, UnicodeDecodeError) as e:
        raise TokenError(f"payload not decodable: {e}") from e
    if not isinstance(claims, dict) or "sub" not in claims:
        raise TokenError("no subject claim")
    return claims


def _body(body):
    if isinstance(body, str):
        body = json.loads(body)
    if not isinstance(body, dict):
        raise ValueError("request body is not a JSON object")
    return body


def _tool_call(body: dict):
    if body.get("method") != "tools/call":
        return None
    params = body.get("params") or {}
    arguments = params.get("arguments")
    return params.get("name"), arguments if isinstance(arguments, dict) else {}


def _header(headers: dict, name: str):
    for key, value in (headers or {}).items():
        if key.lower() == name.lower():
            return value
    return None


def _request_id(event: dict):
    try:
        return _body(event["mcp"]["gatewayRequest"]["body"]).get("id")
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def _reject(request_id, message: str) -> dict:
    return {
        "interceptorOutputVersion": OUTPUT_VERSION,
        "mcp": {"transformedGatewayResponse": {
            "statusCode": 403,
            "body": {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": message}},
        }},
    }


def _pass_request(body: dict) -> dict:
    return {"interceptorOutputVersion": OUTPUT_VERSION, "mcp": {"transformedGatewayRequest": {"body": body}}}


def _pass_response(response: dict) -> dict:
    return {"interceptorOutputVersion": OUTPUT_VERSION, "mcp": {"transformedGatewayResponse": response}}


def _result_payload(result: dict):
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
    others = [item for item in result.get("content", []) if item.get("type") != "text"]
    out["content"] = [{"type": "text", "text": json.dumps(payload)}] + others
    return out


class Handlers:
    def __init__(self, use_case: UseCase):
        self.use_case = use_case
        self.engine = Engine(use_case)
        self.tools = use_case.tools

    # ---- the two interception points

    def request_handler(self, event: dict, context=None) -> dict:
        try:
            request = event["mcp"]["gatewayRequest"]
            body = _body(request.get("body"))
            tool_call = _tool_call(body)
            if tool_call is None:
                return _pass_request(body)
            name, arguments = tool_call
            tool = self.tools.get(name)
            if tool is None:
                return _reject(body.get("id"), f"tool {name} is not governed; no policy covers it")
            claims = claims_of(_header(request.get("headers"), "Authorization"))
            decision = self.engine.decide_request(claims, calls.call(self.use_case, name, arguments))
        except (TokenError, ValueError, KeyError, TypeError) as e:
            log.info("rejected: request could not be evaluated: %s", e)
            return _reject(_request_id(event), f"request could not be evaluated: {e}")
        if decision.allowed:
            return _pass_request(body)
        verb = tool["action"].split("::", 1)[1].strip('"')
        if decision.denied_verb:
            message = f"{verb} is not permitted for this caller"
        else:
            message = f"{verb} rejected; fields not permitted: {', '.join(decision.denied_fields)}"
        log.info("rejected %s: %s", name, message)
        return _reject(body.get("id"), message)

    def response_handler(self, event: dict, context=None) -> dict:
        try:
            request = event["mcp"]["gatewayRequest"]
            response = event["mcp"]["gatewayResponse"]
            tool_call = _tool_call(_body(request.get("body")))
            if tool_call is None or "result" not in (response.get("body") or {}):
                return _pass_response(response)
            name, arguments = tool_call
            tool = self.tools.get(name)
            if tool is None or "returns" not in tool:
                raise ValueError(f"tool {name} declares no result kind")
            claims = claims_of(_header(request.get("headers"), "Authorization"))
            governed = calls.call(self.use_case, name, arguments)
            result = response["body"]["result"]
            decision = self.engine.decide_response(claims, governed, _result_payload(result))
            if governed.returns == "list":
                filtered = decision.rows
            else:
                # An object the caller may not read leaves as an empty
                # object: the call succeeded upstream (a write may have
                # happened) and nothing of the record is shown.
                filtered = decision.rows[0] if decision.rows else {}
        except (TokenError, ValueError, KeyError, TypeError) as e:
            log.info("response withheld: could not be filtered: %s", e)
            return _reject(_request_id(event), f"response withheld; it could not be filtered: {e}")
        if decision.dropped or decision.stripped:
            log.info("filtered %s: dropped %s, stripped %s", name, decision.dropped, decision.stripped)
        body = dict(response["body"])
        body["result"] = _with_payload(result, filtered)
        return _pass_response({**response, "body": body})


def handlers(use_case: UseCase):
    h = Handlers(use_case)
    return h.request_handler, h.response_handler
