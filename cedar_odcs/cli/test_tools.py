"""The tool schema gate: with tools.json beside usecase.py, check fails
when a tool's outputSchema and the contract's leaves differ, and names
both lists."""

import json
import shutil
from pathlib import Path

import pytest

from cedar_odcs.cli.main import main
from cedar_odcs.engine.contract import output_schema_paths

ORDERS = Path(__file__).resolve().parents[2] / "usecases/orders"
LEAVES = ["id", "owner", "status", "total", "shippingAddress", "cardLast4",
          "internalNotes", "fraudScore", "estimatedDelivery"]


def order(leaves):
    return {"type": "object", "properties": {leaf: {"type": "string"} for leaf in leaves}}


def tools(leaves):
    return [{"name": name, "inputSchema": {"type": "object", "properties": {}}, "outputSchema": order(leaves)}
            for name in ("get_order", "update_order", "cancel_order", "refund_order")] + [
        {"name": "list_orders", "inputSchema": {"type": "object", "properties": {}},
         "outputSchema": {"type": "array", "items": order(leaves)}}]


@pytest.fixture
def orders(tmp_path):
    root = tmp_path / "orders"
    shutil.copytree(ORDERS, root, ignore=shutil.ignore_patterns("__pycache__"))
    return root


def test_matching_schemas_pass(orders, capsys):
    (orders / "tools.json").write_text(json.dumps(tools(LEAVES)))
    assert main(["tools", str(orders)]) == 0


def test_a_missing_leaf_fails_check_and_names_it(orders, capsys):
    (orders / "tools.json").write_text(json.dumps(tools([l for l in LEAVES if l != "cardLast4"] + ["discount"])))
    assert main(["check", str(orders), "--skip", "pull", "--skip", "prove"]) == 1
    out = capsys.readouterr().out
    assert "orders___list_orders: outputSchema and the contract differ" in out
    assert "in outputSchema, not in the contract: discount" in out
    assert "in the contract, not in outputSchema: cardLast4" in out
    assert "tools: failed" in out and "== validate ==" not in out


def test_nested_paths_are_spelled_as_the_field_round_spells_them():
    schema = {"type": "object", "properties": {
        "contact": {"type": "object", "properties": {"email": {"type": "string"}}},
        "passengers": {"type": "array", "items": {"type": "object", "properties": {"seat": {"type": "string"}}}},
        "tags": {"type": "array", "items": {"type": "string"}}}}
    assert output_schema_paths(schema) == {"contact.email", "passengers[].seat", "tags"}
