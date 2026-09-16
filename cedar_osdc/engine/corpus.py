"""Runner for the engine-independent test corpus (cedar-integration-tests format).

A use case's test_corpus.py is three lines: collect cases from its
tests/ directory and hand each to check().
"""

import json
from pathlib import Path

import cedarpy
import pytest


def _ref(value):
    if isinstance(value, dict):
        return f'{value["type"]}::"{value["id"]}"'
    return value


def cases(root: Path):
    for spec_file in sorted((root / "tests").glob("*.json")):
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
