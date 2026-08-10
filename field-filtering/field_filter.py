"""The response leg of the interceptor: per-field decisions.

Iteration 1 asked one question per tool call: may this principal read
this object. This iteration asks a second round, one question per
field in the upstream response:

  may User::"alice" ReadOrderField Order::"order-1001",
  where context.field is "cardLast4"?

and strips the fields that come back Deny. Per the settled direction,
the wrapper never rejects a response outright: it removes what it must
and reports what it removed, so the caller can log the removals.

The field classification map lives in the facts, as entity tags on
Contract::"Order". A response field missing from that map fails the
policies' hasTag guard, so no permit matches and it is stripped:
schema drift fails closed.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import cedarpy

HERE = Path(__file__).parent


@dataclass
class Decision:
    allowed: bool
    # Policy ids that produced the decision.
    # Empty on a deny that no policy matched: that is the default deny.
    determining_policies: list


@dataclass
class FilteredResponse:
    body: dict      # the response with denied fields removed
    stripped: list  # field names removed, for the audit log


def load_policies() -> str:
    return (HERE / "policies.cedar").read_text()


def load_entities() -> str:
    return (HERE / "entities.json").read_text()


def is_allowed(principal: str, action: str, resource: str, context: dict = None) -> Decision:
    """principal, action, resource are Cedar entity refs,
    e.g. 'User::"alice"', 'Action::"ReadOrderField"', 'Order::"order-1001"'.
    """
    request = {
        "principal": principal,
        "action": action,
        "resource": resource,
        "context": context or {},
    }
    result = cedarpy.is_authorized(request, load_policies(), load_entities())
    return Decision(
        allowed=(result.decision == cedarpy.Decision.Allow),
        determining_policies=list(result.diagnostics.reasons),
    )


def filter_response(principal: str, resource: str, body: dict) -> FilteredResponse:
    """One ReadOrderField question per field in the upstream response body.

    The field name goes into the request context as a plain string;
    the policies look it up in the contract's tag map to check its
    classification classes.
    """
    kept, stripped = {}, []
    for name, value in body.items():
        decision = is_allowed(
            principal, 'Action::"ReadOrderField"', resource, {"field": name}
        )
        if decision.allowed:
            kept[name] = value
        else:
            stripped.append(name)
    return FilteredResponse(body=kept, stripped=stripped)
