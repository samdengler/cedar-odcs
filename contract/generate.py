"""ODCS to Cedar: the second stage of the build.

One Open Data Contract Standard document goes in; the Cedar artifacts
the policies read come out:

  - the classification map, entity tags on Contract::"<Object>"
  - the writers map, entity tags on Contract::"<Object>/writers"
  - the resource entity declaration for the Cedar schema, with an
    attribute for each property that references a Cedar entity

The policies themselves are hand-written and never name a field; they
look fields up in these maps. So a contract change is a rebuild, never
a policy edit: reclassifying a field, adding one, or changing its
writer changes the generated data only.

The document is validated against the ODCS Pydantic model before
anything is read from it. This module runs at build time only.
"""

import json
from pathlib import Path

import yaml
from open_data_contract_standard.model import OpenDataContractStandard

HERE = Path(__file__).parent

LEVELS = ("public", "internal", "confidential", "restricted")
FIXED_WRITERS = ("owner", "system")


class ContractError(Exception):
    """The contract does not say enough to generate the artifacts."""


def load_contract(text: str) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(yaml.safe_load(text))


def custom(prop, key: str, default=None):
    for cp in prop.customProperties or []:
        if cp.property == key:
            return cp.value
    return default


def contract_entities(contract: OpenDataContractStandard, role_names: set) -> list:
    """The two tag maps per schema object, as Cedar entities."""
    entities = []
    for obj in contract.schema_:
        classification, writers = {}, {}
        for prop in obj.properties:
            if prop.name in classification:
                raise ContractError(f"{obj.name}.{prop.name}: declared twice")
            if prop.classification not in LEVELS:
                raise ContractError(f"{obj.name}.{prop.name}: classification {prop.classification!r}")
            writer = custom(prop, "writer", "system")
            if writer not in FIXED_WRITERS and writer not in role_names:
                raise ContractError(f"{obj.name}.{prop.name}: writer {writer!r} names no role")
            classification[prop.name] = prop.classification
            writers[prop.name] = writer
        entities.append({"uid": {"type": "Contract", "id": obj.name}, "attrs": {}, "parents": [], "tags": classification})
        entities.append({"uid": {"type": "Contract", "id": f"{obj.name}/writers"}, "attrs": {}, "parents": [], "tags": writers})
    return entities


def entity_schema(contract: OpenDataContractStandard) -> str:
    """The resource entity declarations, Cedar schema syntax."""
    out = []
    for obj in contract.schema_:
        attrs = [
            f"  {prop.name}: {custom(prop, 'cedarEntityType')}"
            for prop in obj.properties
            if custom(prop, "cedarEntityType") is not None
        ]
        body = " {\n" + ",\n".join(attrs) + "\n}" if attrs else ""
        out.append(f"entity {obj.name}{body};")
    out.append("entity Contract tags String;")
    return "\n".join(out) + "\n"


def role_names(facts: list) -> set:
    return {e["uid"]["id"] for e in facts if e["uid"]["type"] == "Role"}
