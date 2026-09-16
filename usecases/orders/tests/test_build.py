"""The committed artifacts are what the sources produce, and the maps
carry every entry the hand-written iterations had."""

import json

from cedar_osdc.engine.contract import build
from usecases.orders.usecase import BUILD, ROOT


def test_committed_artifacts_are_current():
    for rel, text in build(ROOT, **BUILD).items():
        assert (ROOT / rel).read_text() == text, f"{rel} is behind its sources; run build.py"


def test_maps_carry_iteration_7():
    prior = {e["uid"]["id"]: e["tags"] for e in json.loads((ROOT / "../../contract/generated/contract.entities.json").read_text())}
    now = {e["uid"]["id"]: e["tags"] for e in json.loads((ROOT / "contract/generated/contract.entities.json").read_text())}
    assert now == prior


def test_policies_are_iteration_9s():
    assert (ROOT / "policies.cedar").read_text() == (ROOT / "../../row-filtering/policies.cedar").read_text()
