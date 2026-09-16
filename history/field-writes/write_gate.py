"""The request leg for field-level writes: the mass assignment defense.

Iteration 2 gated the whole write: may this principal update this
order at all. This iteration asks a second round on the request
payload, one question per field the caller is trying to set:

  may User::"alice" UpdateOrderField Order::"order-1001",
  where context.field is "total"?

and the enforcement move is the inverse of the response leg's. A
response with denied fields is stripped and forwarded; a write with
any denied field is rejected whole, with the denied fields named.
Forwarding the acceptable remainder would apply a request the caller
never made.

One assumption to make explicit: the payload contains only the fields
the caller intends to change (PATCH semantics). A client that echoes
the whole object back, unchanged system fields included, would be
rejected here; that tension is an open question in the design doc.
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
class RequestDecision:
    allowed: bool
    denied_fields: list  # what to name in the rejection


def load_policies() -> str:
    return (HERE / "policies.cedar").read_text()


def load_entities() -> str:
    return (HERE / "entities.json").read_text()


def is_allowed(principal: str, action: str, resource: str, context: dict = None) -> Decision:
    """principal, action, resource are Cedar entity refs,
    e.g. 'User::"alice"', 'Action::"UpdateOrderField"', 'Order::"order-1001"'.
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


def check_request(principal: str, resource: str, body: dict) -> RequestDecision:
    """One UpdateOrderField question per field in the write payload.

    Any denied field rejects the whole request; the caller forwards
    the upstream call only when allowed is True.
    """
    if not isinstance(body, dict) or not body:
        # A write naming no field is not forwarded: the payload round is
        # the only bound on what an update may set.
        return RequestDecision(allowed=False, denied_fields=["<no payload>"])
    denied = [
        name
        for name in body
        if not is_allowed(
            principal, 'Action::"UpdateOrderField"', resource, {"field": name}
        ).allowed
    ]
    return RequestDecision(allowed=not denied, denied_fields=denied)
