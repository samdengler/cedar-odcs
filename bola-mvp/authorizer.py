"""Thin wrapper around the Cedar engine.

This is the whole authorizer. It loads two files:

  policies.cedar  - the rules (who may do what, and when)
  entities.json   - the facts (users, roles, orders, who owns what)

and answers one question:

  is_allowed(principal, action, resource) -> Decision

In the eventual architecture this function is what a Gateway
interceptor or MCP tool handler would call before touching the API.
For now it stands alone so the Cedar part can be understood in
isolation.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import cedarpy

HERE = Path(__file__).parent


@dataclass
class Decision:
    allowed: bool
    # Policy ids (from @id annotations) that produced the decision.
    # Empty on a deny that no policy matched: that is the default deny.
    determining_policies: list


def load_policies() -> str:
    return (HERE / "policies.cedar").read_text()


def load_entities() -> str:
    return (HERE / "entities.json").read_text()


def is_allowed(principal: str, action: str, resource: str) -> Decision:
    """principal, action, resource are Cedar entity refs,
    e.g. 'User::"alice"', 'Action::"ReadOrder"', 'Order::"order-1001"'.
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
