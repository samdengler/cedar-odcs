"""The committed artifacts are what the hand-written contract gives, and
the contract has no catalog behind it."""

from cedar_odcs.engine.contract import build
from cedar_odcs.engine.usecase import paths
from usecases.hr import usecase
from usecases.hr.usecase import CONTRACT, ROOT


def test_committed_artifacts_are_what_the_contract_gives():
    for rel, text in build(ROOT, CONTRACT).items():
        assert (ROOT / rel).read_text() == text, f"{rel} is behind the contract; run build.py"


def test_the_contract_is_written_by_hand():
    assert not hasattr(usecase, "PULL")
    assert not paths(ROOT).unity.exists()
