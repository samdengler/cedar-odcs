"""The hello use case through the handlers: the two callers get the
two views, and the committed artifacts are current."""

import json
from pathlib import Path

from cedar_odcs.engine.contract import build
from cedar_odcs.engine.usecase import paths
from cedar_odcs.gateway.handlers import handlers
from usecases.hello.usecase import BUILD, ROOT, USE_CASE

request_handler, response_handler = handlers(USE_CASE)


def event(name):
    return json.loads((paths(ROOT).events / f"{name}.json").read_text())


def test_committed_artifacts_are_current():
    for rel, text in build(ROOT, **BUILD).items():
        assert (ROOT / rel).read_text() == text, f"{rel} is behind its sources; run build.py"


def test_owner_sees_body_and_not_reviewer_notes():
    out = response_handler(event("response-ada-reads-note-1"))
    payload = out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"]
    assert set(payload) == {"id", "owner", "title", "body"}


def test_reviewer_sees_reviewer_notes_and_not_body():
    out = response_handler(event("response-rae-reads-note-1"))
    payload = out["mcp"]["transformedGatewayResponse"]["body"]["result"]["structuredContent"]
    assert set(payload) == {"id", "owner", "title", "reviewerNotes"}
