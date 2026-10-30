"""The HR tools through the core handlers: an address change decided on
the request before it is forwarded, a record read decided on the
response, one record and its four views, the directory list, and the
HR assistant on the call."""

import json
from pathlib import Path

from cedar_odcs.engine.calls import call
from cedar_odcs.engine.enforce import Engine
from cedar_odcs.gateway.handlers import handlers
from usecases.hr.usecase import TOOLS, USE_CASE

HERE = Path(__file__).parent
request_handler, response_handler = handlers(USE_CASE)

ALICE = json.loads((HERE / "responses" / "alice.json").read_text())
DIRECTORY = ("employeeId", "name", "workEmail", "jobTitle", "department", "manager")


def event(name: str) -> dict:
    return json.loads((HERE / "events" / f"{name}.json").read_text())


def rejection(out: dict) -> str:
    response = out["mcp"]["transformedGatewayResponse"]
    assert response["statusCode"] == 403
    return response["body"]["error"]["message"]


def payload(out: dict) -> dict:
    result = out["mcp"]["transformedGatewayResponse"]["body"]["result"]
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    return result["structuredContent"]


# ---- the request leg

def test_the_record_a_write_changes_is_the_employee_it_names():
    named = call(USE_CASE, "hr___update_employee", {"employeeId": "bob", "changes": {"personalPhone": "x"}})
    assert named.resource == 'Employee::"bob"'
    assert named.context["input"] == {"employeeId": {"__entity": {"type": "User", "id": "bob"}}}


def test_an_employee_changing_their_own_address_is_forwarded():
    out = request_handler(event("request-alice-updates-own-address"))
    assert out["mcp"]["transformedGatewayRequest"]["body"]["params"]["name"] == "hr___update_employee"


def test_an_address_change_carrying_a_raise_is_refused_and_names_the_salary():
    message = rejection(request_handler(event("request-alice-updates-address-and-salary")))
    assert message == "UpdateEmployee rejected; fields not permitted: salary"


def test_an_employee_changing_a_colleagues_address_is_refused_at_the_verb():
    message = rejection(request_handler(event("request-alice-updates-bobs-address")))
    assert message == "UpdateEmployee is not permitted for this caller"


def test_hr_changing_an_address_in_direct_mode_is_refused():
    message = rejection(request_handler(event("request-hana-updates-alices-address")))
    assert message == "UpdateEmployee rejected; fields not permitted: homeAddress.line1"


def test_hr_changing_a_title_is_forwarded():
    assert "transformedGatewayRequest" in request_handler(event("request-hana-updates-alices-title"))["mcp"]


def test_hr_acting_for_the_employee_changes_their_address():
    assert "transformedGatewayRequest" in request_handler(event("request-hana-for-alice-updates-address"))["mcp"]


def test_one_employee_acting_for_another_is_refused():
    message = rejection(request_handler(event("request-alice-for-bob-updates-address")))
    assert message == "UpdateEmployee is not permitted for this caller"


def test_a_whole_address_as_one_value_is_refused():
    ev = event("request-alice-updates-own-address")
    ev["mcp"]["gatewayRequest"]["body"]["params"]["arguments"]["changes"] = {"homeAddress": "48 Pine St, Portland"}
    message = rejection(request_handler(ev))
    assert message == "UpdateEmployee rejected; fields not permitted: homeAddress"


# ---- the response leg

def test_the_employee_sees_their_record_without_hr_notes_or_the_bank_account():
    seen = payload(response_handler(event("response-alice-reads-own-record")))
    assert set(seen) == set(ALICE) - {"hrNotes", "bankAccount"}
    assert seen["homeAddress"] == ALICE["homeAddress"]


def test_a_colleague_sees_the_directory():
    seen = payload(response_handler(event("response-bob-reads-alice")))
    assert seen == {key: ALICE[key] for key in DIRECTORY}


def test_hr_sees_everything_but_the_bank_account():
    seen = payload(response_handler(event("response-hana-reads-alice")))
    assert set(seen) == set(ALICE) - {"bankAccount"}


def test_hr_acting_for_the_employee_sees_what_the_employee_sees():
    seen = payload(response_handler(event("response-hana-for-alice-reads-alice")))
    assert set(seen) == set(ALICE) - {"hrNotes", "bankAccount"}


def test_the_record_an_update_returns_is_filtered_too():
    seen = payload(response_handler(event("response-alice-updates-own-address")))
    assert seen["homeAddress"]["line1"] == "48 Pine St"
    assert "hrNotes" not in seen and "bankAccount" not in seen


# ---- the manager's view

def test_a_manager_sees_a_reports_directory_fields_and_pay():
    seen = payload(response_handler(event("response-maya-reads-alice")))
    assert seen == {key: ALICE[key] for key in DIRECTORY + ("salary",)}


# ---- the directory list

def rows_by_id(out: dict) -> dict:
    return {row["employeeId"]: row for row in payload(out)}


def test_the_list_shows_each_row_as_its_reader_may_see_it():
    rows = rows_by_id(response_handler(event("response-alice-lists-directory")))
    assert list(rows) == ["alice", "bob", "maya", "hana"]
    assert rows["alice"]["homeAddress"] == ALICE["homeAddress"] and rows["alice"]["salary"] == ALICE["salary"]
    for colleague in ("bob", "maya", "hana"):
        assert set(rows[colleague]) <= set(DIRECTORY), colleague
    assert not any("bankAccount" in row or "hrNotes" in row for row in rows.values())


def test_a_manager_listing_sees_pay_on_their_reports_rows_only():
    rows = rows_by_id(response_handler(event("response-maya-lists-directory")))
    assert "salary" in rows["alice"] and "salary" in rows["bob"]
    assert "homeAddress" not in rows["alice"] and "personalPhone" not in rows["bob"]
    assert set(rows["hana"]) <= set(DIRECTORY)
    assert "homeAddress" in rows["maya"]


def test_the_assistant_alone_lists_nothing():
    message = rejection(request_handler(event("request-assistant-alone-lists")))
    assert message == "ListEmployees is not permitted for this caller"


# ---- the HR assistant on the call

def test_the_assistant_is_the_principal_and_the_employee_is_acted_for():
    claims = json.loads((HERE / "identities" / "alice-through-assistant.json").read_text())
    projection = Engine(USE_CASE).projection(claims)
    assert projection.principal == 'Agent::"hr-assistant"'
    assert projection.context == {"actingFor": {"__entity": {"type": "User", "id": "alice"}}}


def test_the_assistant_changes_an_address_for_the_employee_it_talks_with():
    out = request_handler(event("request-alice-through-assistant-updates-own-address"))
    assert "transformedGatewayRequest" in out["mcp"]


def test_the_assistant_shows_the_employee_what_they_see_themself():
    seen = payload(response_handler(event("response-alice-through-assistant-reads-own-record")))
    assert set(seen) == set(ALICE) - {"hrNotes", "bankAccount"}


def test_hr_reads_through_the_assistant_and_changes_nothing_through_it():
    seen = payload(response_handler(event("response-hana-through-assistant-reads-alice")))
    assert set(seen) == set(ALICE) - {"bankAccount"}
    message = rejection(request_handler(event("request-hana-through-assistant-updates-alices-title")))
    assert message == "UpdateEmployee is not permitted for this caller"


def test_the_assistant_alone_reads_and_changes_nothing():
    assert payload(response_handler(event("response-assistant-alone-reads-alice"))) == {}
    message = rejection(request_handler(event("request-assistant-alone-updates-address")))
    assert message == "UpdateEmployee is not permitted for this caller"


# ---- every tool, both legs

BOTH_LEGS = {
    "hr___get_employee": "response-alice-reads-own-record",
    "hr___update_employee": "response-alice-updates-own-address",
    "hr___list_employees": "response-alice-lists-directory",
}


def test_every_tool_has_both_legs_covered():
    assert set(BOTH_LEGS) == set(TOOLS)


def test_both_legs_for_every_tool():
    for name, fixture in BOTH_LEGS.items():
        ev = event(fixture)
        assert "transformedGatewayRequest" in request_handler(ev)["mcp"], name
        seen = payload(response_handler(ev))
        for row in seen if isinstance(seen, list) else [seen]:
            assert "bankAccount" not in row, name
