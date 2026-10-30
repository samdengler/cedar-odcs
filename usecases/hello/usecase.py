"""Hello: notes with an owner and a reviewer, the smallest use case."""

from pathlib import Path

from cedar_odcs.engine.usecase import UseCase

ROOT = Path(__file__).parent

TOOLS = {
    "notes___get_note": {"action": 'Action::"LookupNote"', "id": "noteId", "returns": "object"},
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

CONTRACT = "Note"  # the entity the contract describes: contract/note.odcs.yaml
PULL = dict(contract_id="0f1e2d3c-4b5a-4697-8877-665544332211",
            table_file="notes.table.json", tags_file="notes.column_tags.json")  # the catalog source of that file, for pull
