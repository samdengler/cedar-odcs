"""The reservation contract: nested columns, path-keyed maps, the
attributes the descriptor reads, and the committed artifacts current."""

import json

from core.contract import attributes_of, build, load_contract
from usecases.reservations.usecase import BUILD, ROOT, USE_CASE


def test_committed_artifacts_are_current():
    for rel, text in build(ROOT, **BUILD).items():
        assert (ROOT / rel).read_text() == text, f"{rel} is behind its sources; run build.py"


def test_maps_are_keyed_by_path():
    maps = {e["uid"]["id"]: e["tags"] for e in json.loads((ROOT / "generated/contract.entities.json").read_text())}
    levels = maps["Reservation"]
    assert levels["passengers[].seat"] == "public"
    assert levels["passengers[].passportNumber"] == "restricted"
    assert levels["passengers[].specialServiceRequests"] == "restricted"
    assert levels["contact.email"] == "confidential"
    assert "passengers" not in levels and "contact" not in levels, "containers have no level of their own"
    writers = maps["Reservation/writers"]
    assert writers["passengers[].seat"] == "owner"
    assert writers["passengers[].passportNumber"] == "system"
    assert writers["contact.phone"] == "owner"
    assert writers["remarks"] == "specialist"


def test_descriptor_attributes_come_from_the_contract():
    contract = load_contract((ROOT / "reservation.odcs.yaml").read_text())
    assert attributes_of(contract) == USE_CASE.attributes


def test_schema_declares_the_scalar_attributes():
    schema = (ROOT / "generated/reservation.cedarschema").read_text()
    assert "entity Reservation {\n  recordLocator: String,\n  holderLastName: String\n};" in schema
