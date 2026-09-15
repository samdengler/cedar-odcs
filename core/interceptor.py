"""AgentCore Gateway interceptor handlers, for any use case.

handlers(use_case) returns (request_handler, response_handler) in the
event and result formats the Gateway documents for MCP targets. The
use case's tool table says, per MCP tool name:

  action     the request-leg verb
  id         the argument that names the resource, or
  collection the collection id for a list verb
  payload    the argument holding a write payload, if any
  presented  arguments copied into context as the presented facts,
             e.g. a record locator and a last name, if any
  returns    "object" or "list": what the response leg filters;
             every tool must say

Anything a handler cannot evaluate is rejected or withheld.
"""

import json
import logging

from core.claims import TokenError, claims_of
from core.enforce import ID_PATTERN, Engine
from core.usecase import UseCase

log = logging.getLogger("cedar-osdc")
OUTPUT_VERSION = "1.0"


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

    # ---- what a tool call names

    def _resource(self, tool: dict, arguments: dict) -> str:
        if "collection" in tool:
            return f'Collection::"{tool["collection"]}"'
        value = arguments.get(tool["id"])
        if not isinstance(value, str) or not ID_PATTERN.match(value):
            raise ValueError(f"argument {tool['id']} is missing or not an id")
        return self.engine.resource_ref(value)

    def _context(self, tool: dict, arguments: dict) -> dict:
        if "presented" not in tool:
            return {}
        presented = {}
        for argument, name in tool["presented"].items():
            value = arguments.get(argument)
            if not isinstance(value, str) or not value:
                raise ValueError(f"argument {argument} must be presented")
            # Presented facts are compared upper-cased; the contract
            # states the record holds them that way.
            presented[name] = value.upper()
        return {"presented": presented}

    def _payload(self, tool: dict, arguments: dict):
        expected = set()
        if "id" in tool:
            expected.add(tool["id"])
        if "payload" in tool:
            expected.add(tool["payload"])
        expected |= set(tool.get("presented", {}))
        unexpected = set(arguments) - expected
        if unexpected:
            raise ValueError(f"unexpected arguments: {', '.join(sorted(unexpected))}")
        if "payload" not in tool:
            return None
        payload = arguments.get(tool["payload"])
        if not isinstance(payload, dict) or not payload:
            raise ValueError(f"argument {tool['payload']} must be an object naming the fields to change")
        return payload

    # ---- the two interception points

    def request_handler(self, event: dict, context=None) -> dict:
        try:
            request = event["mcp"]["gatewayRequest"]
            body = _body(request.get("body"))
            call = _tool_call(body)
            if call is None:
                return _pass_request(body)
            name, arguments = call
            tool = self.tools.get(name)
            if tool is None:
                return _reject(body.get("id"), f"tool {name} is not governed; no policy covers it")
            claims = claims_of(_header(request.get("headers"), "Authorization"))
            decision = self.engine.check_call(
                claims, tool["action"], self._resource(tool, arguments),
                self._payload(tool, arguments), self._context(tool, arguments),
            )
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
            call = _tool_call(_body(request.get("body")))
            if call is None or "result" not in (response.get("body") or {}):
                return _pass_response(response)
            name, arguments = call
            tool = self.tools.get(name)
            if tool is None or "returns" not in tool:
                raise ValueError(f"tool {name} declares no result kind")
            claims = claims_of(_header(request.get("headers"), "Authorization"))
            presented = self._context(tool, arguments)
            result = response["body"]["result"]
            payload = _result_payload(result)
            if tool["returns"] == "list":
                if not isinstance(payload, list):
                    raise ValueError("list tool returned no list")
                decision = self.engine.filter_rows(claims, payload, presented)
                filtered = decision.rows
            else:
                if not isinstance(payload, dict):
                    raise ValueError("object tool returned no object")
                decision = self.engine.filter_object(claims, payload, presented)
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
