"""The request leg, assembled: verb round, then payload round.

Iterations 2 and 4 each built one round of the request leg. This
iteration adds verbs that belong to roles, so the first round now
covers function level authorization (API5) as well as object level
(API1): may this principal perform this verb on this order at all.
For an update, the second round from iteration 4 then asks one
question per payload field.

  may User::"dave" RefundOrder Order::"order-1001"?     verb round
  may User::"carol" UpdateOrder Order::"order-2002"?    verb round
  ... and then, for {"internalNotes": "..."}:
  may User::"carol" UpdateOrderField Order::"order-2002",
  where context.field is "internalNotes"?               payload round

A denied verb rejects the call before any field is examined. A denied
field rejects the call whole, with the denied fields named, as in
iteration 4. The upstream API is reached only when both rounds allow.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import cedarpy

HERE = Path(__file__).parent

# Verbs whose payload gets the per-field round. Reads are filtered on
# the response leg instead; cancel and refund carry no payload.
FIELD_ACTIONS = {'Action::"UpdateOrder"': 'Action::"UpdateOrderField"'}


@dataclass
class Decision:
    allowed: bool
    # Policy ids that produced the decision.
    # Empty on a deny that no policy matched: that is the default deny.
    determining_policies: list


@dataclass
class CallDecision:
    allowed: bool
    denied_verb: bool  # the verb round said Deny
    denied_fields: list = field(default_factory=list)  # from the payload round


def load_policies() -> str:
    return (HERE / "policies.cedar").read_text()


def load_entities() -> str:
    return (HERE / "entities.json").read_text()


def is_allowed(principal: str, action: str, resource: str, context: dict = None) -> Decision:
    """principal, action, resource are Cedar entity refs,
    e.g. 'User::"dave"', 'Action::"RefundOrder"', 'Order::"order-1001"'.
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


def check_call(principal: str, action: str, resource: str, body: dict = None) -> CallDecision:
    """The whole request leg for one tool call.

    Round one asks the verb. Round two, for verbs that carry a payload,
    asks one question per field. The caller forwards the upstream call
    only when allowed is True.
    """
    if not is_allowed(principal, action, resource).allowed:
        return CallDecision(allowed=False, denied_verb=True)
    field_action = FIELD_ACTIONS.get(action)
    if field_action is None:
        return CallDecision(allowed=True, denied_verb=False)
    if not isinstance(body, dict) or not body:
        # A write naming no field is not forwarded: the payload round is
        # the only bound on a role-granted update.
        return CallDecision(allowed=False, denied_verb=False, denied_fields=["<no payload>"])
    denied = [
        name
        for name in body
        if not is_allowed(principal, field_action, resource, {"field": name}).allowed
    ]
    return CallDecision(allowed=not denied, denied_verb=False, denied_fields=denied)
