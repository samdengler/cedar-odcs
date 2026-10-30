"""The reservation tool through the core handlers: a read by possession
decided on the response leg, a write on the presented pair before it
is forwarded, nested leaves filtered by path."""

import json
from pathlib import Path

from cedar_odcs.gateway.handlers import handlers
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


# ---- iteration 12: writes by possession, decided on the presented pair

def _error(out):
    return out["mcp"]["transformedGatewayResponse"]["body"]["error"]["message"]


def test_holder_changes_contact_and_seats_by_path():
    out = request_handler(event("request-holder-changes-contact-and-seat"))
    assert "transformedGatewayRequest" in out["mcp"]


def test_wrong_name_write_is_forwarded_for_the_api_to_refuse():
    # The request leg never has the reservation; the pair is presented,
    # and the Reservations API refuses a pair that names no reservation.
    for fixture in ("request-wrong-name-changes-contact", "request-wrong-name-cancels"):
        assert "transformedGatewayRequest" in request_handler(event(fixture))["mcp"], fixture


def test_a_write_without_the_pair_is_refused_before_it_is_forwarded():
    ev = event("request-holder-cancels")
    del ev["mcp"]["gatewayRequest"]["body"]["params"]["arguments"]["lastName"]
    out = request_handler(ev)
    assert out["mcp"]["transformedGatewayResponse"]["statusCode"] == 403
    assert "CancelReservation is not permitted" in _error(out)


def test_fare_change_is_refused_and_named():
    out = request_handler(event("request-holder-changes-fare"))
    assert "fields not permitted: fare" in _error(out)


def test_passenger_name_change_is_refused_by_path():
    out = request_handler(event("request-holder-changes-passenger-name"))
    assert "fields not permitted: passengers[].lastName" in _error(out)


def test_holder_cancels_by_possession():
    assert "transformedGatewayRequest" in request_handler(event("request-holder-cancels"))["mcp"]


def test_unknown_locator_is_forwarded_for_the_api_to_refuse():
    assert "transformedGatewayRequest" in request_handler(event("request-cancel-unknown-record"))["mcp"]


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
        rows = payload if isinstance(payload, list) else [payload]
        for row in rows:
            assert all("passportNumber" not in p for p in row["passengers"]), name


# ---- iteration 13: the specialist's view, the agent as a party, the list

def test_specialist_through_the_agent_reads_any_record_with_remarks():
    assert "transformedGatewayRequest" in request_handler(event("request-specialist-through-agent-looks-up"))["mcp"]
    out = response_handler(event("response-specialist-through-agent-reads"))
    payload = out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"]
    assert payload["remarks"] == "Upgraded at check-in last time"
    assert "contact" in payload
    assert all("passportNumber" not in p for p in payload["passengers"])


def test_specialist_presenting_a_pair_gets_the_customers_view():
    out = response_handler(event("response-specialist-with-pair-reads"))
    payload = out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"]
    assert "remarks" not in payload and "contact" in payload


def test_specialist_writes_remarks_and_not_contact():
    assert "transformedGatewayRequest" in request_handler(event("request-specialist-writes-remarks"))["mcp"]
    out = request_handler(event("request-specialist-changes-contact-without-pair"))
    assert "fields not permitted: contact.email" in _error(out)


def test_specialist_direct_cancels():
    assert "transformedGatewayRequest" in request_handler(event("request-specialist-direct-cancels"))["mcp"]


def test_specialist_lists_and_the_agent_alone_may_not():
    assert "transformedGatewayRequest" in request_handler(event("request-specialist-lists"))["mcp"]
    rows = response_handler(event("response-specialist-lists"))["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"]
    assert [r["recordLocator"] for r in rows] == ["ABC123", "XYZ789"]
    assert request_handler(event("request-agent-alone-lists"))["mcp"]["transformedGatewayResponse"]["statusCode"] == 403


def test_agent_alone_without_a_pair_is_refused():
    assert request_handler(event("request-agent-alone-looks-up-without-pair"))["mcp"]["transformedGatewayResponse"]["statusCode"] == 403


def test_the_agent_is_typed_as_an_agent_and_the_specialist_is_acted_for():
    from cedar_odcs.engine.identities import project

    def identity(name):
        return json.loads((HERE / "identities" / f"{name}.json").read_text())

    p = project(identity("agent"), USE_CASE.entities)
    assert p.principal == 'Agent::"reservations-assistant"' and p.mode == "customer-conversation"
    p = project(identity("sam-through-agent"), USE_CASE.entities)
    assert p.principal == 'Agent::"reservations-assistant"'
    assert p.context == {"actingFor": {"__entity": {"type": "User", "id": "sam"}}}
    assert p.acted_for_entity["parents"] == [{"type": "Role", "id": "specialist"}]
    p = project(identity("sam"), USE_CASE.entities)
    assert p.principal == 'User::"sam"' and p.mode == "employee-direct"


BOTH_LEGS["reservations___list_reservations"] = "response-specialist-lists"
