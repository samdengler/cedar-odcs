"""Orders: the use case the first ten iterations built, on core."""

from pathlib import Path

from core.usecase import UseCase

ROOT = Path(__file__).parent

TOOLS = {
    "orders___get_order":    {"action": 'Action::"ReadOrder"',   "id": "orderId", "returns": "object"},
    "orders___update_order": {"action": 'Action::"UpdateOrder"', "id": "orderId", "payload": "changes", "returns": "object"},
    "orders___cancel_order": {"action": 'Action::"CancelOrder"', "id": "orderId", "returns": "object"},
    "orders___refund_order": {"action": 'Action::"RefundOrder"', "id": "orderId", "returns": "object"},
    "orders___list_orders":  {"action": 'Action::"ListOrders"',  "collection": "orders", "returns": "list"},
}

USE_CASE = UseCase(
    name="orders",
    root=ROOT,
    resource_type="Order",
    attributes={"owner": "User"},
    id_field="id",
    read_action='Action::"ReadOrder"',
    read_field_action='Action::"ReadOrderField"',
    field_actions={'Action::"UpdateOrder"': 'Action::"UpdateOrderField"'},
    tools=TOOLS,
)

# The contract build's inputs for this use case.
BUILD = dict(entity_name="Order", contract_id="7d1d6b2e-2f7a-4d4b-9a1e-3c5e8f0a1b2c",
             table_file="orders.table.json", tags_file="orders.column_tags.json")
