"""The descriptor a use case hands to core."""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UseCase:
    name: str
    root: Path
    # The Cedar entity type a payload row becomes, e.g. "Order".
    resource_type: str
    # Payload field to Cedar type for the fields that become attributes
    # of the resource entity: {"owner": "User"} or {"holderLastName": "String"}.
    # Every other field is looked up in the tag maps and never becomes
    # an attribute. Entity types produce entity references; "String",
    # "Long", and "Bool" produce values.
    attributes: dict
    # The payload field that is the row's id.
    id_field: str
    # The response-leg verbs: the row question and the field question.
    read_action: str
    read_field_action: str
    # Request-leg verbs whose payload gets the field round: verb to
    # field verb, e.g. {'Action::"UpdateOrder"': 'Action::"UpdateOrderField"'}.
    field_actions: dict
    # MCP tool name to how the handlers treat it (see core.interceptor).
    tools: dict = field(default_factory=dict)

    @property
    def policies(self) -> str:
        return (self.root / "policies.cedar").read_text()

    @property
    def entities(self) -> list:
        return json.loads((self.root / "entities.json").read_text())
