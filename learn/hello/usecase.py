"""Hello: notes with an owner and a reviewer, the smallest use case."""

from pathlib import Path

from core.usecase import UseCase

ROOT = Path(__file__).parent

TOOLS = {
    "notes___get_note": {"action": 'Action::"ReadNote"', "id": "noteId", "returns": "object"},
}

USE_CASE = UseCase(
    name="hello",
    root=ROOT,
    resource_type="Note",
    attributes={"owner": "User"},
    id_field="id",
    read_action='Action::"ReadNote"',
    read_field_action='Action::"ReadNoteField"',
    field_actions={},
    tools=TOOLS,
)

BUILD = dict(entity_name="Note", contract_id="0f1e2d3c-4b5a-4697-8877-665544332211",
             table_file="notes.table.json", tags_file="notes.column_tags.json")
