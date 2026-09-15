"""The reservation tool through the core handlers: possession decided on
the response leg, nested leaves filtered by path."""

import json
from pathlib import Path

from core.interceptor import handlers
from usecases.reservations.usecase import USE_CASE

HERE = Path(__file__).parent
request_handler, response_handler = handlers(USE_CASE)


def event(name):
    return json.loads((HERE / "events" / f"{name}.json").read_text())


def test_lookup_with_a_pair_is_forwarded():
    assert "transformedGatewayRequest" in request_handler(event("request-lookup-with-pair"))["mcp"]


def test_lookup_without_a_last_name_is_rejected():
    out = request_handler(event("request-lookup-without-last-name"))
    assert out["mcp"]["transformedGatewayResponse"]["statusCode"] == 403


def test_holder_reads_the_record_at_the_customer_level():
    out = response_handler(event("response-holder-reads-record"))
    payload = out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"]
    assert payload["contact"] == {"email": "ann@example.com", "phone": "+1-404-555-0100"}
    assert [p["seat"] for p in payload["passengers"]] == ["12A", "12B"]
    assert all("passportNumber" not in p and "specialServiceRequests" not in p for p in payload["passengers"])
    assert all("dateOfBirth" in p for p in payload["passengers"])
    assert len(payload["segments"]) == 2
    assert "remarks" not in payload
    assert "fare" in payload and "paymentLast4" in payload


def test_wrong_last_name_gets_nothing():
    out = response_handler(event("response-wrong-last-name"))
    assert out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"] == {}


def test_co_traveler_last_name_gets_nothing():
    out = response_handler(event("response-co-traveler-last-name"))
    assert out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"] == {}


def test_last_name_is_compared_case_insensitively():
    # The fixture presents "Smith"; the record holds "SMITH".
    out = response_handler(event("response-holder-reads-record"))
    assert out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"]["holderLastName"] == "SMITH"
