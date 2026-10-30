"""The committed artifacts are what the sources produce, and the maps
carry every entry the hand-written iterations had."""

import json
import re

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


# Iteration 9's policies, less the three customer writes that now
# compare the customer the call names, plus the lookup verb.
REVISED = {"customer-updates-own-order", "customer-updates-own-order-fields", "customer-cancels-own-order"}
ADDED = ["anyone-looks-up-an-order"]


def _blocks(text: str) -> dict:
    """@id to the policy's text, comments and blank lines removed; a
    policy ends at `};`, or at `);` when it has no conditions."""
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("//")]
    joined = "\n".join(lines) + "\n"
    return {m.group(1): m.group(0) for m in re.finditer(r'@id\("([^"]+)"\)\n.*?\n[)}];\n', joined, re.S)}


def test_policies_are_iteration_9s_with_writes_on_the_request():
    prior = _blocks((ROOT / "../../history/row-filtering/policies.cedar").read_text())
    now = _blocks((ROOT / "policies.cedar").read_text())
    assert list(now) == list(prior) + ADDED
    for policy_id, text in prior.items():
        if policy_id in REVISED:
            assert "resource.owner" in text and "resource.owner" not in now[policy_id], policy_id
            assert "context.input.customerId" in now[policy_id], policy_id
        else:
            assert now[policy_id] == text, policy_id
