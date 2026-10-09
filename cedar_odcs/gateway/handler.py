"""AWS Lambda entry points for the AgentCore Gateway interceptors.

CEDAR_ODCS_USE_CASE names a use case directory (e.g.
usecases/reservations). Handlers(use_case) is built once at import
time, and request/response delegate to its two interception points.
"""

import importlib.util
import os
import sys
from pathlib import Path

from cedar_odcs.gateway.handlers import Handlers


def _load_use_case(directory: str):
    root = Path(directory).resolve()
    spec = importlib.util.spec_from_file_location(f"usecase_{root.name}", root / "usecase.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.USE_CASE


_HANDLERS = Handlers(_load_use_case(os.environ["CEDAR_ODCS_USE_CASE"]))


def request(event, context):
    return _HANDLERS.request_handler(event, context)


def response(event, context):
    return _HANDLERS.response_handler(event, context)
