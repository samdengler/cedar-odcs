"""The build is a function of the catalog: pinned, current, and complete.

The corpus (tests/*.json) pins decisions against entities.json. These
tests pin how entities.json came to be: that the committed artifacts
are what the sources produce, that the contract is a valid ODCS
document, that the generated maps carry every entry iteration 6 wrote
by hand, and that an incomplete catalog fails the build instead of
publishing a gap.
"""

import copy
import json
from pathlib import Path

import pytest

import build
import generate
import unity_import

HERE = Path(__file__).parent


def test_committed_artifacts_are_current():
    for rel, text in build.build().items():
        assert (HERE / rel).read_text() == text, f"{rel} is behind its sources; run build.py"


def test_contract_is_a_valid_odcs_document():
    contract = generate.load_contract((HERE / "order.odcs.yaml").read_text())
    assert contract.apiVersion == "v3.2.0"
    assert contract.schema_[0].name == "Order"
    assert {p.name for p in contract.schema_[0].properties} >= {"id", "owner", "shippingAddress", "fraudScore"}


def test_generated_maps_carry_iteration_6():
    prior = {
        e["uid"]["id"]: e["tags"]
        for e in json.loads((HERE / "../on-behalf-of/entities.json").read_text())
        if e["uid"]["type"] == "Contract"
    }
    now = {
        e["uid"]["id"]: e["tags"]
        for e in json.loads((HERE / "generated/contract.entities.json").read_text())
    }
    for contract_id, tags in prior.items():
        for field_name, value in tags.items():
            assert now[contract_id][field_name] == value, (contract_id, field_name)


def test_generated_schema_extends_the_hand_written_one():
    # Iteration 6's hand-written schema is the generated one up to the
    # verbs added since; the proofs run against the generated file.
    def normalize(text):
        return " ".join(text.split())
    generated = (HERE / "generated/orders.cedarschema").read_text()
    hand_written = (HERE / "../analysis/schemas/on-behalf-of.cedarschema").read_text()
    assert normalize(generated).startswith(normalize(hand_written))
    assert "action ListOrders" in generated


def _fixtures():
    table = json.loads((HERE / "unity/orders.table.json").read_text())
    assignments = json.loads((HERE / "unity/orders.column_tags.json").read_text())
    return table, copy.deepcopy(assignments)


def _drop_tag(assignments, column, key):
    assignments["tag_assignments"] = [
        a for a in assignments["tag_assignments"]
        if not (a["entity_name"].endswith("." + column) and a["tag_key"] == key)
    ]


def test_unclassified_column_fails_the_build():
    table, assignments = _fixtures()
    _drop_tag(assignments, "fraud_score", "classification")
    with pytest.raises(unity_import.ContractError, match="fraud_score has no classification"):
        unity_import.contract_from_unity(table, assignments, "Order", "x")


def test_unknown_level_fails_the_build():
    table, assignments = _fixtures()
    for a in assignments["tag_assignments"]:
        if a["entity_name"].endswith(".fraud_score") and a["tag_key"] == "classification":
            a["tag_value"] = "secret"
    with pytest.raises(unity_import.ContractError, match="'secret'"):
        unity_import.contract_from_unity(table, assignments, "Order", "x")


def test_missing_writer_defaults_to_system():
    contract = generate.load_contract((HERE / "order.odcs.yaml").read_text())
    entities = generate.contract_entities(contract, {"support", "finance", "employee"})
    writers = next(e for e in entities if e["uid"]["id"] == "Order/writers")["tags"]
    assert writers["estimatedDelivery"] == "system"


def test_writer_naming_no_role_fails_the_build():
    contract = generate.load_contract((HERE / "order.odcs.yaml").read_text())
    with pytest.raises(generate.ContractError, match="names no role"):
        generate.contract_entities(contract, role_names=set())


def test_two_columns_becoming_one_field_fails_the_build():
    table, assignments = _fixtures()
    assignments["tag_assignments"].append({
        "entity_type": "columns", "entity_name": "commerce.sales.orders.estimated_delivery",
        "tag_key": "field_name", "tag_value": "fraudScore",
    })
    with pytest.raises(unity_import.ContractError, match="both become field 'fraudScore'"):
        unity_import.contract_from_unity(table, assignments, "Order", "x")


def test_unmapped_column_type_fails_the_build():
    table, assignments = _fixtures()
    table["columns"][0]["type_name"] = "MAP"
    with pytest.raises(unity_import.ContractError, match="maps to no logicalType"):
        unity_import.contract_from_unity(table, assignments, "Order", "x")
