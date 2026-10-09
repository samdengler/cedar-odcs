"""Runner for the engine-independent test corpus (cedar-integration-tests format).

A use case's test_corpus.py is three lines: collect cases from its
test case directory and hand each to check(). The directory is
tests/test-cases/ in the new shape and tests/ in the old; each file's
header names its policies and entities relative to the use case root
in both.

A case's `reason` and `errors` name policies by their `@id`
annotation, not by position; `policy_names` is the policyN -> @id map,
built from a policies.cedar's own order, and `run_case` is what both
this module's `check` and the command line's `run-tests` use to
compare a request's outcome against a case, so the two never drift
apart. A case written the old way, naming policies by position, still
runs: `run_case` accepts either spelling.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import cedarpy
import pytest

from cedar_odcs.engine.usecase import paths


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


def policy_names(policies: str) -> dict:
    """policyN -> the @id annotation, from the file's order."""
    ids = re.findall(r'@id\("([^"]+)"\)', policies)
    return {f"policy{i}": name for i, name in enumerate(ids)}


def name_of(policy_id: str, names: dict) -> str:
    return f"{policy_id} ({names[policy_id]})" if policy_id in names else policy_id


def _positions(ids, names: dict) -> list:
    """A case's reason/errors entries, spelled either as an @id name or
    a policyN position, normalized to the positions Cedar itself
    reports in diagnostics."""
    reverse = {name: position for position, name in names.items()}
    return [reverse.get(i, i) for i in ids]


@dataclass
class CaseResult:
    """One case's request evaluated against its policies and entities,
    with reason/errors normalized to Cedar's own policyN positions."""

    result: object
    actual: str
    reasons: list
    expected_reasons: list
    expected_errors: list
    ok: bool


def run_case(policies: str, entities: str, request_spec: dict) -> CaseResult:
    names = policy_names(policies)
    request = {
        "principal": _ref(request_spec["principal"]),
        "action": _ref(request_spec["action"]),
        "resource": _ref(request_spec["resource"]),
        "context": request_spec.get("context", {}),
    }
    result = cedarpy.is_authorized(request, policies, entities)
    actual = "Allow" if result.decision == cedarpy.Decision.Allow else "Deny"
    reasons = sorted(result.diagnostics.reasons)
    expected_reasons = sorted(_positions(request_spec.get("reason", []), names))
    expected_errors = _positions(request_spec.get("errors", []), names)
    errors_ok = len(result.diagnostics.errors) == len(expected_errors) and all(
        any(policy_id in message for message in result.diagnostics.errors)
        for policy_id in expected_errors
    )
    ok = actual == request_spec["decision"] and reasons == expected_reasons and errors_ok
    return CaseResult(result, actual, reasons, expected_reasons, expected_errors, ok)


def check(policies: str, entities: str, request_spec: dict) -> None:
    case = run_case(policies, entities, request_spec)
    assert case.actual == request_spec["decision"], case.result.diagnostics.errors
    assert case.reasons == case.expected_reasons
    assert len(case.result.diagnostics.errors) == len(case.expected_errors)
    for policy_id in case.expected_errors:
        assert any(policy_id in message for message in case.result.diagnostics.errors)
