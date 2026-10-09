"""The committed artifacts are what the sources produce, and the maps
carry every entry the hand-written iterations had."""

import json

from cedar_odcs.engine.contract import build, pull
from usecases.orders.usecase import CONTRACT, PULL, ROOT


def test_committed_contract_is_what_the_catalog_fixtures_give():
    for rel, text in pull(ROOT, CONTRACT, **PULL).items():
        assert (ROOT / rel).read_text() == text, f"{rel} is behind the catalog fixtures; run build.py"


def test_committed_artifacts_are_what_the_contract_gives():
    for rel, text in build(ROOT, CONTRACT).items():
        assert (ROOT / rel).read_text() == text, f"{rel} is behind the contract; run build.py"


def test_maps_carry_iteration_7():
    prior = {e["uid"]["id"]: e["tags"] for e in json.loads((ROOT / "../../history/contract/generated/contract.entities.json").read_text())}
    now = {e["uid"]["id"]: e["tags"] for e in json.loads((ROOT / "contract/generated/contract.entities.json").read_text())}
    assert now == prior


def test_policies_are_iteration_9s():
    assert (ROOT / "policies.cedar").read_text() == (ROOT / "../../history/row-filtering/policies.cedar").read_text()
