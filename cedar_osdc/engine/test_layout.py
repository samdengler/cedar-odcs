"""Both shapes of a use case folder read the same.

The reservations use case, committed in the new shape, is copied into
a temporary directory in the old shape, file by file, reversing the
move. The build, the test case runner, and the descriptor's fetch are
then asked for the same things twice, once against the committed
folder and once against the old-shaped copy. The engine keeps reading
the old shape for as long as anything still uses it; this test is
what says the two agree.
"""

import json
import shutil
from pathlib import Path

import pytest

from cedar_osdc.engine.contract import build
from cedar_osdc.engine.corpus import cases
from cedar_osdc.engine.usecase import layout, paths, responses_fetch
from usecases.reservations.usecase import BUILD

NEW = Path(__file__).resolve().parents[2] / "usecases/reservations"

AT_THE_ROOT = ("usecase.py", "policies.cedar", "principals.cedarschema",
               "actions.cedarschema", "facts.json", "entities.json", "build.py")


@pytest.fixture(scope="module")
def old(tmp_path_factory) -> Path:
    """usecases/reservations in the old shape, as it was before the move."""
    root = tmp_path_factory.mktemp("reservations")
    shutil.copytree(NEW / "contract/unity", root / "unity")
    shutil.copytree(NEW / "contract/generated", root / "generated")
    shutil.copy(NEW / "contract/reservation.odcs.yaml", root / "reservation.odcs.yaml")
    shutil.copytree(NEW / "tests/test-cases", root / "tests")
    shutil.copytree(NEW / "tests/identities", root / "callers")
    shutil.copytree(NEW / "tests/responses", root / "records")
    shutil.copytree(NEW / "tests/events", root / "events")
    for name in AT_THE_ROOT:
        shutil.copy(NEW / name, root / name)
    return root


def test_the_contract_directory_is_what_tells_the_shapes_apart(old):
    assert layout(NEW) == "new"
    assert layout(old) == "old"
    assert paths(NEW).unity == NEW / "contract/unity"
    assert paths(old).unity == old / "unity"


def test_the_build_writes_under_contract_in_the_new_shape_and_at_the_root_in_the_old(old):
    new_outputs = build(NEW, **BUILD)
    old_outputs = build(old, **BUILD)
    assert set(new_outputs) == {
        "contract/reservation.odcs.yaml",
        "contract/generated/contract.entities.json",
        "contract/generated/entities.cedarschema",
        "contract/generated/reservation.cedarschema",
        "entities.json",
    }
    assert set(old_outputs) == {
        "reservation.odcs.yaml",
        "generated/contract.entities.json",
        "generated/entities.cedarschema",
        "generated/reservation.cedarschema",
        "entities.json",
    }
    # Same content apart from the contract's header line, which names
    # the fixture path.
    for key in ("generated/contract.entities.json", "generated/entities.cedarschema",
                "generated/reservation.cedarschema"):
        assert new_outputs["contract/" + key] == old_outputs[key]
    assert new_outputs["entities.json"] == old_outputs["entities.json"]
    strip = lambda text: "\n".join(l for l in text.splitlines() if not l.startswith("#"))
    assert strip(new_outputs["contract/reservation.odcs.yaml"]) == strip(old_outputs["reservation.odcs.yaml"])


def test_the_test_cases_are_found_in_both_shapes(old):
    ids_new = [p.id for p in cases(NEW)]
    ids_old = [p.id for p in cases(old)]
    assert ids_new and ids_new == ids_old


def test_the_fetch_reads_one_saved_response_per_record(old):
    for root in (NEW, old):
        fetch = responses_fetch(root)
        assert fetch("ABC123")["holderLastName"] == "SMITH"
        assert fetch("QQQ000") is None
        assert fetch("../entities") is None
