"""The handlers and the command line reach the same decision.

The engine owns what a tool call means; the two interfaces only
translate. This test takes every fixture event of every use case,
translates it twice, once the way the interceptor does and once the
way `--tool` and `--arg` do, and compares the engine's values: the
Call, the CallDecision, and, for an event that carries a tool result,
the RowsDecision. Printed words and Gateway envelopes are not
compared; the handler tests and the command line tests pin those.

The second pair of tests keeps the refusal wording in one place: the
engine's `explain`, which both interfaces call.
"""

import json
from pathlib import Path

import pytest

from cedar_osdc.cli.main import _pairs, load_use_case, main
from cedar_osdc.engine import calls
from cedar_osdc.engine.enforce import Engine, explain
from cedar_osdc.engine.usecase import paths
from cedar_osdc.gateway import handlers

REPO = Path(__file__).resolve().parents[1]

USE_CASES = {
    "hello": REPO / "learn/hello",
    "orders": REPO / "usecases/orders",
    "reservations": REPO / "usecases/reservations",
}


def _typed(value) -> str:
    """One `--arg key=value` string as a person would type it: a
    string as itself, anything else as JSON."""
    return value if isinstance(value, str) else json.dumps(value)


def _outcome(use_case, tool_name: str, arguments: dict):
    """The Call, or the refusal the interfaces turn into a rejection."""
    try:
        return calls.call(use_case, tool_name, arguments)
    except (ValueError, KeyError, TypeError) as e:
        return (type(e).__name__, str(e))


@pytest.mark.parametrize("name", sorted(USE_CASES))
def test_the_interfaces_translate_every_event_the_same_way(name, capsys):
    root = USE_CASES[name]
    use_case = load_use_case(str(root)).USE_CASE
    engine = Engine(use_case)
    compared = skipped = 0
    for path in sorted(paths(root).events.glob("*.json")):
        event = json.loads(path.read_text())
        request = event["mcp"]["gatewayRequest"]
        # The handler's own reading of the event, not a second copy of it.
        body = handlers._body(request.get("body"))
        tool_call = handlers._tool_call(body)
        if tool_call is None:
            skipped += 1
            continue
        tool_name, arguments = tool_call
        if tool_name not in use_case.tools:
            skipped += 1
            continue
        claims = handlers.claims_of(handlers._header(request.get("headers"), "Authorization"))

        by_handler = _outcome(use_case, tool_name, arguments)
        typed = [f"{key}={_typed(value)}" for key, value in arguments.items()]
        by_command_line = _outcome(use_case, tool_name, _pairs(typed))
        assert by_handler == by_command_line, f"{path.name}: the two interfaces build different calls"
        compared += 1
        if not isinstance(by_handler, calls.Call):
            continue  # both refuse the call, in the same words

        assert (engine.decide_request(claims, by_handler)
                == engine.decide_request(claims, by_command_line)), f"{path.name}: request leg"
        response = event["mcp"].get("gatewayResponse")
        if response and "result" in (response.get("body") or {}):
            payload = handlers._result_payload(response["body"]["result"])
            assert (engine.decide_response(claims, by_handler, payload)
                    == engine.decide_response(claims, by_command_line, payload)), f"{path.name}: response leg"

    with capsys.disabled():
        print(f"\n  {name}: {compared} events compared, {skipped} not tool calls or not governed")
    assert compared, f"{name} compared no events; the fixtures or the tool table moved"


# ---- the refusal wording lives in the engine

TEMPLATES = ("is not permitted for this caller", "fields not permitted:")


def test_the_handlers_take_their_refusal_words_from_the_engine():
    source = (REPO / "cedar_osdc/gateway/handlers.py").read_text()
    for template in TEMPLATES:
        assert template not in source, f"handlers.py spells {template!r} itself"

    use_case = load_use_case(str(USE_CASES["reservations"])).USE_CASE
    engine = Engine(use_case)
    request_handler, _ = handlers.handlers(use_case)
    for fixture in ("request-wrong-name-changes-contact", "request-holder-changes-fare"):
        event = json.loads((paths(USE_CASES["reservations"]).events / f"{fixture}.json").read_text())
        request = event["mcp"]["gatewayRequest"]
        name, arguments = handlers._tool_call(handlers._body(request["body"]))
        claims = handlers.claims_of(handlers._header(request["headers"], "Authorization"))
        call = calls.call(use_case, name, arguments)
        words = explain(call, engine.decide_request(claims, call))
        out = request_handler(event)
        assert out["mcp"]["transformedGatewayResponse"]["body"]["error"]["message"] == words
    assert words.startswith("UpdateReservation rejected; fields not permitted: fare")


def test_the_command_line_takes_its_refusal_words_from_the_engine(capsys):
    source = (REPO / "cedar_osdc/cli/main.py").read_text()
    for template in TEMPLATES:
        assert template not in source, f"cli/main.py spells {template!r} itself"

    directory = str(USE_CASES["reservations"])
    caller = str(paths(USE_CASES["reservations"]).identities / "agent.json")
    use_case = load_use_case(directory).USE_CASE
    engine = Engine(use_case)
    claims = json.loads(Path(caller).read_text())
    refusals = [
        (["--tool", "reservations___cancel_reservation",
          "--arg", "recordLocator=ABC123", "--arg", "lastName=Jones"],
         {"recordLocator": "ABC123", "lastName": "Jones"}, "reservations___cancel_reservation"),
        (["--tool", "reservations___update_reservation",
          "--arg", "recordLocator=ABC123", "--arg", "lastName=Smith",
          "--arg", 'changes={"fare": 1.0}'],
         {"recordLocator": "ABC123", "lastName": "Smith", "changes": {"fare": 1.0}},
         "reservations___update_reservation"),
    ]
    for argv, arguments, tool_name in refusals:
        call = calls.call(use_case, tool_name, arguments)
        words = explain(call, engine.decide_request(claims, call))
        assert main(["dry-run", directory, "--caller", caller] + argv) == 1
        assert f"Request    rejected: {words}\n" in capsys.readouterr().out
    assert words == "UpdateReservation rejected; fields not permitted: fare"


def test_the_engine_is_where_the_words_are_spelled():
    source = (REPO / "cedar_osdc/engine/enforce.py").read_text()
    for template in TEMPLATES:
        assert source.count(template) == 1
