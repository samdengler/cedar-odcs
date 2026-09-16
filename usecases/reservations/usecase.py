"""Reservations: possession of a record locator and the holder's last name."""

import json
from pathlib import Path

from cedar_osdc.engine.usecase import UseCase

ROOT = Path(__file__).parent

PRESENTED = {"recordLocator": "locator", "lastName": "lastName"}

TOOLS = {
    "reservations___get_reservation": {
        "action": 'Action::"LookupReservation"',
        "id": "recordLocator", "presented": PRESENTED, "returns": "object",
    },
    "reservations___update_reservation": {
        "action": 'Action::"UpdateReservation"',
        "id": "recordLocator", "presented": PRESENTED, "payload": "changes", "returns": "object",
    },
    "reservations___cancel_reservation": {
        "action": 'Action::"CancelReservation"',
        "id": "recordLocator", "presented": PRESENTED, "returns": "object",
    },
    "reservations___list_reservations": {
        "action": 'Action::"ListReservations"',
        "collection": "reservations", "returns": "list",
    },
}

RECORDS = json.loads((ROOT / "records.json").read_text())


def fetch(record_locator: str):
    """The read path, stood in for by a fixture: what the reservations
    API returns for a locator, or None. The interceptor calls this
    before a write by possession is forwarded."""
    return RECORDS.get(record_locator)

USE_CASE = UseCase(
    name="reservations",
    root=ROOT,
    resource_type="Reservation",
    attributes={"recordLocator": "String", "holderLastName": "String"},
    id_field="recordLocator",
    read_action='Action::"ReadReservation"',
    read_field_action='Action::"ReadReservationField"',
    field_actions={'Action::"UpdateReservation"': 'Action::"UpdateReservationField"'},
    tools=TOOLS,
    prefetch_actions={'Action::"UpdateReservation"', 'Action::"CancelReservation"'},
    fetch=fetch,
)

BUILD = dict(entity_name="Reservation", contract_id="c0a8f1e2-5b3d-4e6f-9a7b-8c9d0e1f2a3b",
             table_file="reservations.table.json", tags_file="reservations.column_tags.json")
