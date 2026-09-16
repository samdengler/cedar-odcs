"""Both shapes of a use case folder read the same.

The reservations use case is copied into a temporary directory in the
new shape, file by file, the way the move will do it. The build, the
test case runner, and the descriptor's fetch are then asked for the
same things twice, once against the copy and once against the
committed folder, which is still in the old shape. This is what holds
while the three use cases move one at a time.
"""

import json
import shutil
from pathlib import Path

import pytest

from cedar_osdc.engine.contract import build, write
from cedar_osdc.engine.corpus import cases
from cedar_osdc.engine.usecase import layout, paths, responses_fetch
from usecases.reservations.usecase import BUILD

OLD = Path(__file__).resolve().parents[2] / "usecases/reservations"

AT_THE_ROOT = ("usecase.py", "policies.cedar", "principals.cedarschema",
               "actions.cedarschema", "facts.json", "entities.json", "build.py")


@pytest.fixture(scope="module")
def new(tmp_path_factory) -> Path:
    """usecases/reservations in the new shape, as the move will leave it."""
    root = tmp_path_factory.mktemp("reservations")
    shutil.copytree(OLD / "unity", root / "contract/unity")
    shutil.copytree(OLD / "generated", root / "contract/generated")
    shutil.copy(OLD / "reservation.odcs.yaml", root / "contract/reservation.odcs.yaml")
    shutil.copytree(OLD / "tests", root / "tests/test-cases")
    shutil.copytree(OLD / "callers", root / "tests/identities")
    shutil.copytree(OLD / "records", root / "tests/responses")
    shutil.copytree(OLD / "events", root / "tests/events")
    for name in AT_THE_ROOT:
        shutil.copy(OLD / name, root / name)
    return root


def test_the_contract_directory_is_what_tells_the_shapes_apart(new):
    assert layout(new) == "new"
    assert layout(OLD) == "old"
    assert paths(new).unity == new / "contract/unity"
    assert paths(OLD).unity == OLD / "unity"


def test_the_build_writes_under_contract_and_entities_at_the_root(new):
    outputs = build(new, **BUILD)
    assert set(outputs) == {
        "contract/reservation.odcs.yaml",
        "contract/generated/contract.entities.json",
        "contract/generated/entities.cedarschema",
        "contract/generated/reservation.cedarschema",
        "entities.json",
    }
    write(new, outputs)
    assert (new / "contract/generated/reservation.cedarschema").exists()
    assert not (new / "generated").exists() and not (new / "reservation.odcs.yaml").exists()

    old = build(OLD, **BUILD)
    assert set(old) == {"reservation.odcs.yaml", "generated/contract.entities.json",
                        "generated/entities.cedarschema", "generated/reservation.cedarschema",
                        "entities.json"}
    # The same build from the same fixtures: everything but the header
    # line naming where the fixtures were read from.
    for key, text in old.items():
        moved = f"contract/{key}" if key != "entities.json" else key
        assert outputs[moved] == text.replace("unity/", "contract/unity/")
    assert (new / "entities.json").read_text() == (OLD / "entities.json").read_text()


def test_the_test_cases_are_found_under_tests(new):
    assert [c.id for c in cases(new)] == [c.id for c in cases(OLD)]
    assert sorted(p.name for p in paths(new).test_cases.glob("*.json")) == [
        "reservation-specialist.json", "reservation-writes.json", "reservations.json"]


def test_the_fetch_reads_one_saved_response_per_record(new):
    fetch = responses_fetch(new)
    record = fetch("ABC123")
    assert record["holderLastName"] == "SMITH"
    assert record == json.loads((new / "tests/responses/ABC123.json").read_text())
    assert fetch("no-such-locator") is None
    assert fetch("../entities") is None
