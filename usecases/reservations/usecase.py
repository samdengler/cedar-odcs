"""Reservations: possession of a record locator and the holder's last name."""

from pathlib import Path

from core.usecase import UseCase

ROOT = Path(__file__).parent

TOOLS = {
    "reservations___get_reservation": {
        "action": 'Action::"LookupReservation"',
        "id": "recordLocator",
        "presented": {"recordLocator": "locator", "lastName": "lastName"},
        "returns": "object",
    },
}

USE_CASE = UseCase(
    name="reservations",
    root=ROOT,
    resource_type="Reservation",
    attributes={"recordLocator": "String", "holderLastName": "String"},
    id_field="recordLocator",
    read_action='Action::"ReadReservation"',
    read_field_action='Action::"ReadReservationField"',
    field_actions={},
    tools=TOOLS,
)

BUILD = dict(entity_name="Reservation", contract_id="c0a8f1e2-5b3d-4e6f-9a7b-8c9d0e1f2a3b",
             table_file="reservations.table.json", tags_file="reservations.column_tags.json")
