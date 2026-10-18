"""CEDAR_ODCS_RECORD: with it set, each handler logs its inbound event
as one JSON line; without it, nothing of the event is logged."""

import json
import logging
from pathlib import Path

from cedar_odcs.gateway.handlers import handlers
from usecases.orders.usecase import USE_CASE

EVENTS = Path(__file__).resolve().parents[2] / "usecases/orders/tests/events"
request_handler, response_handler = handlers(USE_CASE)


def event(name: str) -> dict:
    return json.loads((EVENTS / f"{name}.json").read_text())


def test_recording_logs_each_event_as_one_json_line(monkeypatch, caplog):
    monkeypatch.setenv("CEDAR_ODCS_RECORD", "1")
    caplog.set_level(logging.DEBUG, logger="cedar-odcs")
    request_handler(event("request-alice-reads-own-order"))
    response_handler(event("response-alice-reads-own-order"))
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("record ")]
    assert [line.split(" ", 2)[1] for line in lines] == ["request", "response"]
    assert json.loads(lines[0].split(" ", 2)[2]) == event("request-alice-reads-own-order")


def test_without_the_switch_no_event_is_logged(monkeypatch, caplog):
    monkeypatch.delenv("CEDAR_ODCS_RECORD", raising=False)
    caplog.set_level(logging.DEBUG, logger="cedar-odcs")
    request_handler(event("request-alice-reads-own-order"))
    assert not [r for r in caplog.records if r.getMessage().startswith("record ")]
