"""The contract build, for any use case: Unity Catalog to ODCS to Cedar.

Stage one merges two Unity Catalog API responses, the table and its
column tag assignments, into an ODCS v3.2.0 document. Nested columns
(struct, array of struct) come from the column's type_json and become
nested ODCS properties. Column tags read, by key:

  classification          public | internal | confidential | restricted;
                          applies to the column and every leaf under it
  classification__a__b    the level of leaf a.b under this column
  writer, writer__a__b    owner | system | <role name>, same scoping
  field_name              the API field name for the column
  cedar_entity_type       the column references a Cedar entity of this type
  cedar_attribute_type    the column is a scalar attribute: String, Long, Bool

Unity tags attach to columns only, so a nested leaf's level travels in
the tag key: classification__passportNumber on the passengers column
is the level of passengers[].passportNumber.

Stage two validates the document and emits the tag maps, keyed by
path (contact.email, passengers[].seat), and the resource entity
declaration. An unclassified leaf fails the build; a missing writer
means system. Runs at build time only.
"""

import json
from pathlib import Path

import yaml
from open_data_contract_standard.model import OpenDataContractStandard

from cedar_odcs.engine.usecase import paths

LEVELS = ("public", "internal", "confidential", "restricted")
FIXED_WRITERS = ("owner", "system")
CONTRACT_VERSION = "v3.2.0"
LOGICAL_TYPES = {
    "STRING": "string", "INT": "integer", "LONG": "integer", "SHORT": "integer",
    "DECIMAL": "number", "DOUBLE": "number", "FLOAT": "number", "BOOLEAN": "boolean",
    "DATE": "date", "TIMESTAMP": "timestamp", "STRUCT": "object", "ARRAY": "array",
}
SPARK_TYPES = {
    "string": "string", "integer": "integer", "long": "integer", "short": "integer",
    "double": "number", "float": "number", "boolean": "boolean", "date": "date",
    "timestamp": "timestamp",
}


class ContractError(Exception):
    """The catalog or the contract does not say enough."""


def camel(column: str) -> str:
    head, *rest = column.split("_")
    return head + "".join(part.capitalize() for part in rest)


# ---------------------------------------------------------------- stage one

def column_tags(assignments: dict) -> dict:
    tags = {}
    for a in assignments["tag_assignments"]:
        if a["entity_type"] != "columns":
            continue
        if "." not in a["entity_name"]:
            raise ContractError(f"tag assignment on {a['entity_name']!r} names no column")
        column = a["entity_name"].rsplit(".", 1)[1]
        tags.setdefault(column, {})[a["tag_key"]] = a["tag_value"]
    return tags


def _scoped(tags: dict, key: str, path: list):
    """The most specific tag for key at path: key__a__b, then key__a, then key."""
    for depth in range(len(path), -1, -1):
        candidate = "__".join([key] + path[:depth])
        if candidate in tags:
            return tags[candidate]
    return None


def _leaf_custom(tags: dict, path: list) -> list:
    writer = _scoped(tags, "writer", path) or "system"
    custom = [{"property": "writer", "value": writer}]
    if not path:
        if "cedar_entity_type" in tags:
            custom.append({"property": "cedarEntityType", "value": tags["cedar_entity_type"]})
        if "cedar_attribute_type" in tags:
            custom.append({"property": "cedarAttributeType", "value": tags["cedar_attribute_type"]})
    return custom


def _classify(column: str, tags: dict, path: list) -> str:
    level = _scoped(tags, "classification", path)
    where = ".".join([column] + path)
    if level is None:
        raise ContractError(f"column {where} has no classification tag")
    if level not in LEVELS:
        raise ContractError(f"column {where} has classification {level!r}, not one of {LEVELS}")
    return level


def _spark_property(column: str, tags: dict, name: str, spark_type, path: list, nullable: bool) -> dict:
    """One ODCS property from a Spark schema node, nested as needed."""
    prop = {"name": name if not path else camel(name), "required": not nullable}
    if isinstance(spark_type, dict) and spark_type.get("type") == "struct":
        prop["logicalType"] = "object"
        prop["properties"] = [
            _spark_property(column, tags, f["name"], f["type"], path + [f["name"]], f.get("nullable", True))
            for f in spark_type["fields"]
        ]
        return prop
    if isinstance(spark_type, dict) and spark_type.get("type") == "array":
        element = spark_type["elementType"]
        prop["logicalType"] = "array"
        if isinstance(element, dict) and element.get("type") == "struct":
            prop["items"] = {
                "logicalType": "object",
                "properties": [
                    _spark_property(column, tags, f["name"], f["type"], path + [f["name"]], f.get("nullable", True))
                    for f in element["fields"]
                ],
            }
            return prop
        prop["items"] = {"logicalType": SPARK_TYPES[element]}
    else:
        if spark_type not in SPARK_TYPES:
            raise ContractError(f"column {column}.{'.'.join(path)} has type {spark_type!r}, which maps to no logicalType")
        prop["logicalType"] = SPARK_TYPES[spark_type]
    prop["classification"] = _classify(column, tags, path)
    prop["customProperties"] = _leaf_custom(tags, path)
    return prop


def property_from_column(column: dict, tags: dict) -> dict:
    name = column["name"]
    type_name = column["type_name"]
    if type_name not in LOGICAL_TYPES:
        raise ContractError(f"column {name} has type {type_name!r}, which maps to no logicalType")
    field_name = tags.get("field_name", camel(name))
    if type_name in ("STRUCT", "ARRAY"):
        spark = json.loads(column["type_json"])["type"]
        prop = _spark_property(name, tags, field_name, spark, [], column["nullable"])
    else:
        prop = {
            "name": field_name,
            "logicalType": LOGICAL_TYPES[type_name],
            "required": not column["nullable"],
            "classification": _classify(name, tags, []),
            "customProperties": _leaf_custom(tags, []),
        }
    prop["physicalName"] = name
    prop["physicalType"] = column["type_text"]
    if column.get("comment"):
        prop["description"] = column["comment"]
    return prop


def contract_from_unity(table: dict, assignments: dict, entity_name: str, contract_id: str) -> dict:
    tags = column_tags(assignments)
    properties = [
        property_from_column(c, tags.get(c["name"], {}))
        for c in sorted(table["columns"], key=lambda c: c["position"])
    ]
    seen = {}
    for prop in properties:
        if prop["name"] in seen:
            raise ContractError(f"columns {seen[prop['name']]} and {prop['physicalName']} both become field {prop['name']!r}")
        seen[prop["name"]] = prop["physicalName"]
    return {
        "apiVersion": CONTRACT_VERSION,
        "kind": "DataContract",
        "id": contract_id,
        "name": table["full_name"],
        "version": "1.0.0",
        "status": "active",
        "domain": table["schema_name"],
        "description": {"purpose": table.get("comment", "")},
        "servers": [{"server": "unity", "type": "databricks", "host": "dbc-example.cloud.databricks.com",
                     "catalog": table["catalog_name"], "schema": table["schema_name"]}],
        "schema": [{"name": entity_name, "physicalName": table["name"], "physicalType": "table",
                    "description": table.get("comment", ""), "properties": properties}],
        "customProperties": [
            {"property": "sourceCatalog", "value": "unity-catalog"},
            {"property": "sourceTable", "value": table["full_name"]},
        ],
    }


def render(contract: dict, sources: str) -> str:
    header = (f"# Generated by the contract build from {sources} at build time.\n"
              "# Do not edit; change the column tags in Unity Catalog and rebuild.\n")
    return header + yaml.safe_dump(contract, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------- stage two

def load_contract(text: str) -> OpenDataContractStandard:
    return OpenDataContractStandard.model_validate(yaml.safe_load(text))


def custom(prop, key: str, default=None):
    for cp in prop.customProperties or []:
        if cp.property == key:
            return cp.value
    return default


def _leaves(props, prefix: str):
    """(path, property) for every leaf under props."""
    for prop in props:
        path = f"{prefix}{prop.name}"
        if prop.logicalType == "object" and prop.properties:
            yield from _leaves(prop.properties, path + ".")
        elif prop.logicalType == "array" and prop.items is not None and prop.items.properties:
            yield from _leaves(prop.items.properties, path + "[].")
        else:
            yield path, prop


def contract_entities(contract: OpenDataContractStandard, role_names: set) -> list:
    entities = []
    for obj in contract.schema_:
        classification, writers = {}, {}
        for path, prop in _leaves(obj.properties, ""):
            if path in classification:
                raise ContractError(f"{obj.name}.{path}: declared twice")
            if prop.classification not in LEVELS:
                raise ContractError(f"{obj.name}.{path}: classification {prop.classification!r}")
            writer = custom(prop, "writer", "system")
            if writer not in FIXED_WRITERS and writer not in role_names:
                raise ContractError(f"{obj.name}.{path}: writer {writer!r} names no role")
            classification[path] = prop.classification
            writers[path] = writer
        entities.append({"uid": {"type": "Contract", "id": obj.name}, "attrs": {}, "parents": [], "tags": classification})
        entities.append({"uid": {"type": "Contract", "id": f"{obj.name}/writers"}, "attrs": {}, "parents": [], "tags": writers})
    return entities


def entity_schema(contract: OpenDataContractStandard) -> str:
    out = []
    for obj in contract.schema_:
        attrs = []
        for prop in obj.properties:
            entity_type = custom(prop, "cedarEntityType")
            attribute_type = custom(prop, "cedarAttributeType")
            if entity_type is not None:
                attrs.append(f"  {prop.name}: {entity_type}")
            elif attribute_type is not None:
                attrs.append(f"  {prop.name}: {attribute_type}")
        body = " {\n" + ",\n".join(attrs) + "\n}" if attrs else ""
        out.append(f"entity {obj.name}{body};")
    out.append("entity Contract tags String;")
    return "\n".join(out) + "\n"


def attributes_of(contract: OpenDataContractStandard) -> dict:
    """The descriptor's attributes map, from the contract."""
    out = {}
    for obj in contract.schema_:
        for prop in obj.properties:
            t = custom(prop, "cedarEntityType") or custom(prop, "cedarAttributeType")
            if t is not None:
                out[prop.name] = t
    return out


def role_names(facts: list) -> set:
    return {e["uid"]["id"] for e in facts if e["uid"]["type"] == "Role"}


# ---------------------------------------------------------------- the build

def build(root: Path, entity_name: str, contract_id: str, table_file: str, tags_file: str) -> dict:
    """Every output as {relative path: text}, without writing.

    Inputs under root: the two Unity fixtures, facts.json,
    principals.cedarschema, actions.cedarschema. The Unity fixtures
    and the generated files sit under contract/ in the new shape and
    at the root in the old; `paths` knows which folder is which, and
    the keys returned here follow it. entities.json is at the root in
    both.
    """
    place = paths(root)
    table = json.loads((place.unity / table_file).read_text())
    assignments = json.loads((place.unity / tags_file).read_text())
    unity = place.relative(place.unity)
    contract_text = render(contract_from_unity(table, assignments, entity_name, contract_id),
                           f"{unity}/{table_file} and {unity}/{tags_file}")
    contract = load_contract(contract_text)
    facts = json.loads((place.root / "facts.json").read_text())
    entities = contract_entities(contract, role_names(facts))
    schema = ((place.root / "principals.cedarschema").read_text() + entity_schema(contract) + "\n"
              + (place.root / "actions.cedarschema").read_text())
    stem = entity_name.lower()
    generated = place.relative(place.generated)
    return {
        place.relative(place.contract_dir / f"{stem}.odcs.yaml"): contract_text,
        f"{generated}/contract.entities.json": json.dumps(entities, indent=2) + "\n",
        f"{generated}/entities.cedarschema": entity_schema(contract),
        f"{generated}/{stem}.cedarschema": schema,
        "entities.json": json.dumps(facts + entities, indent=2) + "\n",
    }


def write(root: Path, outputs: dict) -> None:
    for rel, text in outputs.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
