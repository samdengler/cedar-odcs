"""The command line against the reservations use case: every command
runs, and its words match the decisions the corpus and the handlers
already pin."""

import json
from pathlib import Path

import pytest

from cedar_osdc.cli.main import main, playground_link
from cedar_osdc.engine.usecase import paths

REPO = Path(__file__).resolve().parents[2]
R = str(REPO / "usecases/reservations")
FIXTURES = paths(REPO / "usecases/reservations")


@pytest.fixture
def caller(tmp_path):
    def write(name):
        path = tmp_path / f"{name}.json"
        path.write_text((FIXTURES.identities / f"{name}.json").read_text())
        return str(path)
    return write


def run(capsys, *argv):
    code = main(list(argv))
    return code, capsys.readouterr().out


def test_run_tests_reports_every_case(capsys):
    code, out = run(capsys, "run-tests", R)
    assert code == 0
    assert "43 passed, 0 failed" in out
    assert "PASS  the record is readable when locator and holder last name are the presented ones" in out


def test_run_tests_exports_the_cedar_format(capsys, tmp_path):
    out_file = tmp_path / "cases.json"
    code, _ = run(capsys, "run-tests", R, "--cedar-tests", str(out_file))
    assert code == 0
    cases = json.loads(out_file.read_text())
    assert cases[0]["decision"] in ("allow", "deny") and "entities" in cases[0]


def test_authorize_names_the_policy(capsys):
    code, out = run(capsys, "authorize", R, "--principal", 'User::"sam"',
                    "--action", 'Action::"ReadReservation"', "--resource", 'Reservation::"ABC123"')
    assert code == 0
    assert out.startswith("Allow") and "specialist-reads-any-reservation" in out


def test_dry_run_reports_both_legs(capsys, caller, tmp_path):
    record = tmp_path / "record.json"
    record.write_text((FIXTURES.responses / "ABC123.json").read_text())
    code, out = run(capsys, "dry-run", R, "--caller", caller("agent"), "--tool", "reservations___get_reservation",
                    "--arg", "recordLocator=ABC123", "--arg", "lastName=Smith", "--response", str(record))
    assert code == 0
    assert "Request    forwarded" in out
    assert "stripped: passengers[].passportNumber, passengers[].specialServiceRequests, remarks" in out


def test_dry_run_rejects_in_words(capsys, caller):
    code, out = run(capsys, "dry-run", R, "--caller", caller("agent"), "--tool", "reservations___cancel_reservation",
                    "--arg", "recordLocator=ABC123", "--arg", "lastName=Jones")
    assert code == 1
    assert "rejected: CancelReservation is not permitted" in out


def test_check_access_for_the_pair_and_the_specialist(capsys, caller):
    code, out = run(capsys, "check-access", R, "--caller", caller("agent"),
                    "--presented", "locator=ABC123", "--presented", "lastName=Smith")
    assert code == 0
    assert "Verbs held      LookupReservation, ReadReservation, UpdateReservation, CancelReservation\n" in out
    assert "Writable        passengers[].seat (owner), contact.email (owner), contact.phone (owner)" in out
    assert "remarks (internal)" in out.split("Not readable")[1].split("\n")[0]
    code, out = run(capsys, "check-access", R, "--caller", caller("sam-through-agent"))
    assert "acting for sam" in out and "ListReservations" in out.split("Verbs held")[1].split("\n")[0]
    assert "Writable        remarks (specialist)" in out


def test_share_builds_a_playground_link(capsys):
    code, out = run(capsys, "share", R, "--case", "co-traveler's last name is not")
    assert code == 0
    assert "https://www.cedarpolicy.com/en/playground#data:" in out


def test_playground_link_round_trips():
    import base64, gzip
    link = playground_link("permit(principal, action, resource);", "entity User;", "[]",
                           {"principal": 'User::"a"', "action": 'Action::"b"', "resource": 'User::"c"', "context": {}})
    blob = link.split("#data:", 1)[1]
    state = json.loads(gzip.decompress(base64.b64decode(blob)))
    assert state["interfaceVersion"] == 1 and state["playgroundData"]["principal"] == {"type": "User", "id": "a"}


def test_a_directory_without_a_use_case_is_a_usage_error(capsys, tmp_path):
    assert main(["run-tests", str(tmp_path)]) == 2
