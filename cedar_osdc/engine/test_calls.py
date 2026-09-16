"""What a tool call names, against the reservations tool table: the
values both interfaces hand the engine, and the calls neither may
forward."""

from dataclasses import replace

import pytest

from cedar_osdc.engine.calls import call
from usecases.reservations.usecase import USE_CASE


def test_a_pair_is_carried_as_context():
    c = call(USE_CASE, "reservations___get_reservation",
             {"recordLocator": "ABC123", "lastName": "Smith"})
    assert c.action == 'Action::"LookupReservation"'
    assert c.resource == 'Reservation::"ABC123"'
    assert c.payload is None
    assert c.context == {"presented": {"locator": "ABC123", "lastName": "SMITH"}}
    assert c.row_id == "ABC123"
    assert c.returns == "object"


def test_a_locator_alone_presents_no_pair():
    # The locator is one half of the pair; alone it is the resource
    # and nothing more.
    c = call(USE_CASE, "reservations___get_reservation", {"recordLocator": "ABC123"})
    assert c.resource == 'Reservation::"ABC123"' and c.context == {}


def test_half_a_pair_cannot_be_evaluated():
    # The reservation tools' pair is the locator and the last name,
    # and the locator is also the id: a call missing the locator is
    # refused for its resource first. Two facts beside the id show
    # the partial pair itself.
    two_facts = replace(USE_CASE, tools={"reservations___get_reservation": {
        "action": 'Action::"LookupReservation"', "id": "recordLocator",
        "presented": {"lastName": "lastName", "firstName": "firstName"},
        "returns": "object",
    }})
    with pytest.raises(ValueError, match="presented facts incomplete: firstName missing"):
        call(two_facts, "reservations___get_reservation",
             {"recordLocator": "ABC123", "lastName": "Smith"})


def test_an_argument_the_table_does_not_name_is_refused():
    with pytest.raises(ValueError, match="unexpected arguments: patch"):
        call(USE_CASE, "reservations___update_reservation",
             {"recordLocator": "ABC123", "lastName": "Smith", "patch": {"remarks": "x"}})


def test_an_update_without_its_payload_is_refused():
    with pytest.raises(ValueError, match="argument changes must be an object"):
        call(USE_CASE, "reservations___update_reservation",
             {"recordLocator": "ABC123", "lastName": "Smith"})


def test_a_list_names_the_collection_and_no_row():
    c = call(USE_CASE, "reservations___list_reservations", {})
    assert c.action == 'Action::"ListReservations"'
    assert c.resource == 'Collection::"reservations"'
    assert c.row_id is None and c.context == {} and c.payload is None
    assert c.returns == "list"


def test_a_tool_the_table_does_not_name_is_refused():
    with pytest.raises(ValueError, match="not governed"):
        call(USE_CASE, "reservations___delete_everything", {"recordLocator": "ABC123"})
