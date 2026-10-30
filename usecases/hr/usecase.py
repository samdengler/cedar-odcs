"""HR: an employee updates their own home address; colleagues see the
directory; a manager sees their reports' pay; HR keeps the rest."""

from pathlib import Path

from cedar_odcs.engine.usecase import UseCase

ROOT = Path(__file__).parent

# The record is the employee. employeeId is the id of the record a call
# names and, copied into context.input as a User, the employee the call
# is for: one argument, so a write names no employee but the one whose
# record it changes. A read names no one: the response leg decides it
# on the record the API returns, its employeeId and its manager.
EMPLOYEE = {"employeeId": "User"}

TOOLS = {
    "hr___get_employee":    {"action": 'Action::"LookupEmployee"', "id": "employeeId", "returns": "object"},
    "hr___update_employee": {"action": 'Action::"UpdateEmployee"', "id": "employeeId", "input": EMPLOYEE, "payload": "changes", "returns": "object"},
    "hr___list_employees":  {"action": 'Action::"ListEmployees"', "collection": "employees", "returns": "list"},
}

USE_CASE = UseCase(
    name="hr",
    root=ROOT,
    resource_type="Employee",
    attributes={"employeeId": "User", "manager": "User"},
    id_field="employeeId",
    read_action='Action::"ReadEmployee"',
    read_field_action='Action::"ReadEmployeeField"',
    field_actions={'Action::"UpdateEmployee"': 'Action::"UpdateEmployeeField"'},
    tools=TOOLS,
)

# The contract build's input. The HR system has no catalog this project
# reads, so there is no PULL: contract/employee.odcs.yaml is written by hand.
CONTRACT = "Employee"
