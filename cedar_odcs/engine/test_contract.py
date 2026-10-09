"""The contract is the file the build reads: a use case with no catalog
builds from a hand-written one, and a contract that says too little or
the wrong thing fails the build rather than the policies."""

import shutil
from pathlib import Path

import pytest

from cedar_odcs.engine.contract import ContractError, build, contract_path, pull
from usecases.hello.usecase import CONTRACT, PULL, ROOT


@pytest.fixture
def by_hand(tmp_path) -> Path:
    """hello with its catalog fixtures removed: the contract is all there is."""
    root = tmp_path / "hello"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    shutil.rmtree(root / "contract/unity")
    return root


def test_a_contract_with_no_catalog_builds_the_same_artifacts(by_hand):
    assert build(by_hand, CONTRACT) == build(ROOT, CONTRACT)


def test_there_is_nothing_to_pull_without_the_catalog(by_hand):
    with pytest.raises(FileNotFoundError):
        pull(by_hand, CONTRACT, **PULL)


def test_a_missing_contract_names_the_file(by_hand):
    contract_path(by_hand, CONTRACT).unlink()
    with pytest.raises(ContractError, match="contract/note.odcs.yaml is missing"):
        build(by_hand, CONTRACT)


def test_a_level_outside_the_four_fails_the_build(by_hand):
    document = contract_path(by_hand, CONTRACT)
    document.write_text(document.read_text().replace("classification: confidential", "classification: secret"))
    with pytest.raises(ContractError, match="Note.body: classification 'secret'"):
        build(by_hand, CONTRACT)


def test_a_writer_that_names_no_role_fails_the_build(by_hand):
    document = contract_path(by_hand, CONTRACT)
    document.write_text(document.read_text().replace("value: reviewer", "value: auditor"))
    with pytest.raises(ContractError, match="writer 'auditor' names no role"):
        build(by_hand, CONTRACT)
