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


# ---- iteration 12: writes by possession, verified by the pre-fetch

def _error(out):
    return out["mcp"]["transformedGatewayResponse"]["body"]["error"]["message"]


def test_holder_changes_contact_and_seats_by_path():
    out = request_handler(event("request-holder-changes-contact-and-seat"))
    assert "transformedGatewayRequest" in out["mcp"]


def test_wrong_name_is_refused_before_the_write_is_forwarded():
    out = request_handler(event("request-wrong-name-changes-contact"))
    assert out["mcp"]["transformedGatewayResponse"]["statusCode"] == 403
    assert "UpdateReservation is not permitted" in _error(out)


def test_fare_change_is_refused_and_named():
    out = request_handler(event("request-holder-changes-fare"))
    assert "fields not permitted: fare" in _error(out)


def test_passenger_name_change_is_refused_by_path():
    out = request_handler(event("request-holder-changes-passenger-name"))
    assert "fields not permitted: passengers[].lastName" in _error(out)


def test_holder_cancels_by_possession():
    assert "transformedGatewayRequest" in request_handler(event("request-holder-cancels"))["mcp"]


def test_wrong_name_cannot_cancel():
    assert request_handler(event("request-wrong-name-cancels"))["mcp"]["transformedGatewayResponse"]["statusCode"] == 403


def test_no_record_no_write():
    out = request_handler(event("request-cancel-unknown-record"))
    assert out["mcp"]["transformedGatewayResponse"]["statusCode"] == 403


BOTH_LEGS = {
    "reservations___get_reservation": "response-holder-reads-record",
    "reservations___update_reservation": "response-holder-changes-contact-and-seat",
    "reservations___cancel_reservation": "response-holder-cancels",
}


def test_every_tool_has_both_legs_covered():
    from usecases.reservations.usecase import TOOLS
    assert set(BOTH_LEGS) == set(TOOLS)


def test_both_legs_for_every_tool():
    for name, fixture in BOTH_LEGS.items():
        ev = event(fixture)
        assert "transformedGatewayRequest" in request_handler(ev)["mcp"], name
        out = response_handler(ev)["mcp"]["transformedGatewayResponse"]
        assert out["statusCode"] == 200, name
        payload = out["body"]["result"]["structuredContent"]
        assert "remarks" not in payload and all("passportNumber" not in p for p in payload["passengers"]), name
