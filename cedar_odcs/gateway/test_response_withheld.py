"""A tools/call response can carry data in more places than the record.
The response handler decides one payload field by field, so anything
else the response holds leaves out: a tool's error text, content items
that are not the payload, and any other key of the result or the body.
A restricted value in any of them would otherwise reach the client with
no decision made about it."""

import copy
import json
from pathlib import Path

from cedar_odcs.gateway.handlers import TOOL_ERROR, handlers
from usecases.orders.usecase import USE_CASE

EVENTS = Path(__file__).resolve().parents[2] / "usecases/orders/tests/events"
_, response_handler = handlers(USE_CASE)
SECRET = "4111 1111 1111 1111"


def event() -> dict:
    return json.loads((EVENTS / "response-alice-reads-own-order.json").read_text())


def result_of(e: dict) -> dict:
    return e["mcp"]["gatewayResponse"]["body"]["result"]


def transformed(e: dict) -> dict:
    out = response_handler(copy.deepcopy(e))["mcp"]["transformedGatewayResponse"]
    assert SECRET not in json.dumps(out), out
    return out


def with_body(body) -> dict:
    e = event()
    e["mcp"]["gatewayResponse"]["body"] = body
    return e


def withheld(e: dict) -> str:
    out = transformed(e)
    assert out["statusCode"] == 403
    return out["body"]["error"]["message"]


# ---- a tool's error

def test_a_tools_error_keeps_its_code_and_id_and_loses_its_text():
    out = transformed(with_body({"jsonrpc": "2.0", "id": 7, "error": {
        "code": -32001, "message": f"lookup failed for {SECRET}", "data": {"card": SECRET}}}))
    assert out["body"] == {"jsonrpc": "2.0", "id": 7, "error": {"code": -32001, "message": TOOL_ERROR}}


def test_an_error_keeps_the_status_the_gateway_gave_it():
    e = with_body({"jsonrpc": "2.0", "id": 7, "error": {"code": -32001, "message": SECRET}})
    e["mcp"]["gatewayResponse"]["statusCode"] = 502
    assert transformed(e)["statusCode"] == 502


def test_an_error_with_no_usable_code_takes_the_servers_generic_one():
    for error in ({"code": SECRET, "message": "x"}, SECRET, None):
        out = transformed(with_body({"jsonrpc": "2.0", "id": 7, "error": error}))
        assert out["body"]["error"] == {"code": -32000, "message": TOOL_ERROR}


def test_a_result_beside_an_error_leaves_with_it():
    out = transformed(with_body({"jsonrpc": "2.0", "id": 7, "error": {"code": 1, "message": "x"},
                                 "result": {"content": [{"type": "text", "text": SECRET}]}}))
    assert "result" not in out["body"]


def failed(**beside) -> dict:
    """A tool failure as a Lambda function target reports it (observed on
    applied-odcs, November 2026): a result with isError true and a text
    item holding the runtime's error, which has no record id."""
    text = json.dumps({"errorMessage": f"lookup failed for {SECRET}", "errorType": "ValueError",
                       "requestId": "r-1", "stackTrace": [f"line 1, card {SECRET}"]})
    return with_body({"jsonrpc": "2.0", "id": 7, "result": {
        "isError": True, "content": [{"type": "text", "text": text}], **beside}})


FAILED = {"isError": True, "content": [{"type": "text", "text": TOOL_ERROR}]}


def test_a_failure_reported_in_the_result_says_so_and_loses_its_text():
    out = transformed(failed())
    assert out["statusCode"] == 200
    assert out["body"] == {"jsonrpc": "2.0", "id": 7, "result": FAILED}


def test_a_failure_with_text_that_is_not_json_gets_the_same_message():
    e = failed()
    result_of(e)["content"][0]["text"] = f"lookup failed for {SECRET}"
    assert transformed(e)["body"]["result"] == FAILED


def test_a_failure_holding_a_whole_record_gets_the_same_message():
    e = event()
    result_of(e)["isError"] = True
    result_of(e)["structuredContent"] = {"id": "order-1001", "owner": "alice", "total": SECRET}
    assert transformed(e)["body"]["result"] == FAILED


# ---- what a result holds beside the payload

def test_content_items_that_are_not_the_payload_leave():
    e = event()
    result_of(e)["content"] += [
        {"type": "resource", "resource": {"uri": "file:///card", "text": SECRET}},
        {"type": "image", "data": "aW1hZ2U=", "mimeType": "image/png", "annotations": {"card": SECRET}},
        {"type": "text", "text": SECRET},
    ]
    content = transformed(e)["body"]["result"]["content"]
    assert [item["type"] for item in content] == ["text"]
    assert json.loads(content[0]["text"])["id"] == "order-1001"


def test_other_keys_of_the_result_leave():
    e = event()
    result_of(e).update({"_meta": {"card": SECRET}, "card": SECRET})
    assert not {"_meta", "card"} & set(transformed(e)["body"]["result"])


def test_is_error_stays_only_as_a_boolean():
    e = event()
    result_of(e)["isError"] = False
    assert transformed(e)["body"]["result"]["isError"] is False
    result_of(e)["isError"] = SECRET
    assert "isError" not in transformed(e)["body"]["result"]


def test_other_keys_of_the_body_leave():
    e = event()
    e["mcp"]["gatewayResponse"]["body"]["card"] = SECRET
    assert set(transformed(e)["body"]) == {"jsonrpc", "id", "result"}


# ---- a response the handler cannot read

def test_a_body_that_is_not_an_object_is_withheld():
    for body in (f"card {SECRET}", [SECRET]):
        assert "could not be filtered" in withheld(with_body(body))


def test_a_body_with_neither_a_result_nor_an_error_is_withheld():
    assert "could not be filtered" in withheld(with_body({"jsonrpc": "2.0", "id": 7, "card": SECRET}))


def test_a_result_that_is_not_an_object_is_withheld():
    assert "could not be filtered" in withheld(with_body({"jsonrpc": "2.0", "id": 7, "result": f"card {SECRET}"}))


def test_a_content_item_that_is_not_an_object_is_withheld():
    assert "could not be filtered" in withheld(with_body(
        {"jsonrpc": "2.0", "id": 7, "result": {"content": [f"card {SECRET}"]}}))


def test_a_result_with_nothing_to_filter_is_withheld():
    assert "could not be filtered" in withheld(with_body({"jsonrpc": "2.0", "id": 7, "result": {
        "content": [{"type": "resource", "resource": {"uri": "file:///card", "text": SECRET}}]}}))


# ---- what stays as it was

def test_a_tools_call_response_with_no_body_passes():
    e = event()
    del e["mcp"]["gatewayResponse"]["body"]
    e["mcp"]["gatewayResponse"]["statusCode"] = 202
    out = transformed(e)
    assert out["statusCode"] == 202 and "body" not in out


def test_another_methods_response_passes_as_it_came():
    for body in ({"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "x"}], "_meta": {"a": 1}}},
                 {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "no such method"}}):
        e = with_body(body)
        e["mcp"]["gatewayRequest"]["body"] = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        assert transformed(e)["body"] == body
