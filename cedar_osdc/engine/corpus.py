"""Runner for the engine-independent test corpus (cedar-integration-tests format).

A use case's test_corpus.py is three lines: collect cases from its
test case directory and hand each to check(). The directory is
tests/test-cases/ in the new shape and tests/ in the old; each file's
header names its policies and entities relative to the use case root
in both.
"""

import json
from pathlib import Path

import cedarpy
import pytest

from cedar_osdc.engine.usecase import paths


def _ref(value):
    if isinstance(value, dict):
        return f'{value["type"]}::"{value["id"]}"'
    return value


def case_files(root: Path) -> list:
    """Every test case file of a use case, in a stable order."""
    return sorted(paths(root).test_cases.glob("*.json"))


def cases(root: Path):
    for spec_file in case_files(root):
        spec = json.loads(spec_file.read_text())
        policies = (root / spec["policies"]).read_text()
        entities = (root / spec["entities"]).read_text()
        for request in spec["requests"]:
            yield pytest.param(policies, entities, request, id=f'{spec_file.stem}: {request["description"]}')


def check(policies: str, entities: str, request_spec: dict) -> None:
    request = {
        "principal": _ref(request_spec["principal"]),
        "action": _ref(request_spec["action"]),
        "resource": _ref(request_spec["resource"]),
        "context": request_spec.get("context", {}),
    }
    result = cedarpy.is_authorized(request, policies, entities)
    actual = "Allow" if result.decision == cedarpy.Decision.Allow else "Deny"
    assert actual == request_spec["decision"], result.diagnostics.errors
    assert sorted(result.diagnostics.reasons) == sorted(request_spec.get("reason", []))
    expected_errors = request_spec.get("errors", [])
    assert len(result.diagnostics.errors) == len(expected_errors)
    for policy_id in expected_errors:
        assert any(policy_id in message for message in result.diagnostics.errors)
