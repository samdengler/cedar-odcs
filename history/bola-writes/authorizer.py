"""The request-leg gate: writes are checked before the call goes out.

Iteration 1's read check can run on the response leg, because a
response that comes back can still be filtered or discarded. A write
cannot wait: once the upstream API applies UpdateOrder, the damage is
done. So this check runs before the call is forwarded, and a Deny
rejects the whole call. Nothing is stripped on the request leg;
silently dropping part of a write would apply a request the caller
never made.

The ownership fact the policy needs (order.owner) must therefore be
known before the upstream call. entities.json stands in for the two
real options: an entity store the decision point consults, or a
pre-fetch of the object through the read path.
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


def load_policies() -> str:
    return (HERE / "policies.cedar").read_text()


def load_entities() -> str:
    return (HERE / "entities.json").read_text()


def is_allowed(principal: str, action: str, resource: str) -> Decision:
    """principal, action, resource are Cedar entity refs,
    e.g. 'User::"alice"', 'Action::"UpdateOrder"', 'Order::"order-1001"'.

    On the request leg the caller forwards the upstream call only when
    this returns allowed; a deny means the call is rejected whole.
    """
    request = {
        "principal": principal,
        "action": action,
        "resource": resource,
        "context": {},
    }
    result = cedarpy.is_authorized(request, load_policies(), load_entities())
    return Decision(
        allowed=(result.decision == cedarpy.Decision.Allow),
        determining_policies=list(result.diagnostics.reasons),
    )
