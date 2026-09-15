"""The build: Unity Catalog to ODCS to Cedar, in one command.

    uv run python build.py

Stage one reads the recorded Unity Catalog responses in unity/ and
writes order.odcs.yaml. Stage two validates that document and writes
generated/contract.entities.json and generated/order.entities.cedarschema.
The build then assembles the files the runtime and the prover read:

  entities.json              facts.json + the generated contract entities
  generated/orders.cedarschema
                             principals.cedarschema + the generated entity
                             declarations + actions.cedarschema

Everything written here is committed, so the diff of a rebuild is the
review of a contract change. test_build.py fails when the committed
files are behind the sources.
"""

import json
from pathlib import Path

import generate
import unity_import

HERE = Path(__file__).parent


def build() -> dict:
    """Every output as {relative path: text}, without writing."""
    contract_text = unity_import.import_orders()
    contract = generate.load_contract(contract_text)
    facts = json.loads((HERE / "facts.json").read_text())
    entities = generate.contract_entities(contract, generate.role_names(facts))
    schema = (
        (HERE / "principals.cedarschema").read_text()
        + generate.entity_schema(contract)
        + "\n"
        + (HERE / "actions.cedarschema").read_text()
    )
    return {
        "order.odcs.yaml": contract_text,
        "generated/contract.entities.json": json.dumps(entities, indent=2) + "\n",
        "generated/order.entities.cedarschema": generate.entity_schema(contract),
        "generated/orders.cedarschema": schema,
        "entities.json": json.dumps(facts + entities, indent=2) + "\n",
    }


def write(outputs: dict) -> None:
    for rel, text in outputs.items():
        path = HERE / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


if __name__ == "__main__":
    outputs = build()
    write(outputs)
    for rel in outputs:
        print("wrote", rel)
