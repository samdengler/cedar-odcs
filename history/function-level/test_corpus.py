"""Runner for data-driven Cedar test cases.

The cases live in tests/*.json and follow the format of the Cedar
project's own integration-test corpus (cedar-integration-tests on
GitHub): a policy file, an entities file, and a list of requests with
expected decision, determining policies, and evaluation errors.

This file is the Python runner. A Rust runner can execute the same
JSON files against the Rust engine without changes, which is the point:
the tests describe the governance rules, not the implementation.
"""

import json
from pathlib import Path

import cedarpy
import pytest

HERE = Path(__file__).parent
TEST_DIR = HERE / "tests"


def _ref(value):
    """Entity ref: {"type": "User", "id": "alice"} -> User::"alice"."""
    if isinstance(value, dict):
        return f'{value["type"]}::"{value["id"]}"'
    return value


def _cases():
    for spec_file in sorted(TEST_DIR.glob("*.json")):
        spec = json.loads(spec_file.read_text())
        policies = (HERE / spec["policies"]).read_text()
        entities = (HERE / spec["entities"]).read_text()
        for request in spec["requests"]:
            yield pytest.param(
                policies, entities, request,
                id=f'{spec_file.stem}: {request["description"]}',
            )


@pytest.mark.parametrize("policies,entities,request_spec", list(_cases()))
def test_case(policies, entities, request_spec):
    request = {
        "principal": _ref(request_spec["principal"]),
        "action": _ref(request_spec["action"]),
        "resource": _ref(request_spec["resource"]),
        "context": request_spec.get("context", {}),
    }
    result = cedarpy.is_authorized(request, policies, entities)

    expected = request_spec["decision"]
    actual = "Allow" if result.decision == cedarpy.Decision.Allow else "Deny"
    assert actual == expected, result.diagnostics.errors

    assert sorted(result.diagnostics.reasons) == sorted(request_spec.get("reason", []))

    expected_errors = request_spec.get("errors", [])
    assert len(result.diagnostics.errors) == len(expected_errors)
    for policy_id in expected_errors:
        assert any(policy_id in message for message in result.diagnostics.errors)
