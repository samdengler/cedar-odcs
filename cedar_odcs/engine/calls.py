"""What a tool call names, for any use case.

call(use_case, tool_name, arguments) turns one MCP tool call into the
terms the engine decides on. The use case's tool table says, per MCP
tool name:

  action     the request-leg verb
  id         the argument that names the resource, or
  collection the collection id for a list verb
  payload    the argument holding a write payload, if any
  presented  arguments copied into context as the presented facts,
             e.g. a record locator and a last name, if any
  returns    "object" or "list": what the response leg filters;
             every tool must say

A call the table does not name, an id the engine cannot use, an
argument the table does not name, and half a pair of presented facts
all raise ValueError. An interface turns that into a rejection:
anything that cannot be evaluated is not forwarded.
"""

from dataclasses import dataclass

from cedar_odcs.engine.enforce import ID_PATTERN
from cedar_odcs.engine.usecase import UseCase


@dataclass
class Call:
    """One tool call in the engine's terms, whatever the interface."""

    action: str      # 'Action::"UpdateReservation"'
    resource: str    # 'Reservation::"ABC123"' or 'Collection::"orders"'
    payload: dict | None
    context: dict    # the presented facts, upper-cased, or empty
    row_id: str | None
    returns: str | None = None  # "object" or "list"


def call(use_case: UseCase, tool_name: str, arguments: dict) -> Call:
    tool = use_case.tools.get(tool_name)
    if tool is None:
        raise ValueError(f"tool {tool_name} is not governed; no policy covers it")
    return Call(
        action=tool["action"],
        resource=_resource(use_case, tool, arguments),
        payload=_payload(tool, arguments),
        context=_context(tool, arguments),
        row_id=arguments.get(tool["id"]) if "id" in tool else None,
        returns=tool.get("returns"),
    )


def _resource(use_case: UseCase, tool: dict, arguments: dict) -> str:
    if "collection" in tool:
        return f'Collection::"{tool["collection"]}"'
    value = arguments.get(tool["id"])
    if not isinstance(value, str) or not ID_PATTERN.match(value):
        raise ValueError(f"argument {tool['id']} is missing or not an id")
    return f'{use_case.resource_type}::"{value}"'


def _context(tool: dict, arguments: dict) -> dict:
    """The presented facts, when the call presents them. A tool
    that declares them accepts a call without them: the policies
    then decide on the caller's own grants, a specialist's view,
    and a customer's call falls to the lookup's default deny. A
    partial pair is an error."""
    if "presented" not in tool:
        return {}
    values = {name: arguments.get(argument) for argument, name in tool["presented"].items()}
    given = {name: v for name, v in values.items() if isinstance(v, str) and v}
    # The resource id can double as one half of the pair; the pair
    # is presented when the other half is. A locator alone is a
    # call without a pair.
    id_names = {name for argument, name in tool["presented"].items() if argument == tool.get("id")}
    if not (set(given) - id_names):
        return {}
    if len(given) != len(values):
        missing = sorted(set(values) - set(given))
        raise ValueError(f"presented facts incomplete: {', '.join(missing)} missing")
    # Presented facts are compared upper-cased; the contract states
    # the record holds them that way.
    return {"presented": {name: v.upper() for name, v in given.items()}}


def _payload(tool: dict, arguments: dict):
    expected = set()
    if "id" in tool:
        expected.add(tool["id"])
    if "payload" in tool:
        expected.add(tool["payload"])
    expected |= set(tool.get("presented", {}))
    unexpected = set(arguments) - expected
    if unexpected:
        raise ValueError(f"unexpected arguments: {', '.join(sorted(unexpected))}")
    if "payload" not in tool:
        return None
    payload = arguments.get(tool["payload"])
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"argument {tool['payload']} must be an object naming the fields to change")
    return payload
