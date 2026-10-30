# HR

An employee record, the employee who changes their own home address
on it, colleagues who read the directory, a manager who reads their
reports' pay, an HR partner who keeps the rest, and the HR assistant,
an agent, that does all of it for whoever it talks with. The three
earlier use cases pull their contract from Unity Catalog; this one
writes it by hand, at `contract/employee.odcs.yaml`, as a use case
with no catalog does, and `check` has no pull step.

## The record is the employee

The record's id, `employeeId`, is the employee's own user id, the
subject of their token, and the record carries it as an attribute
typed `User`. `update_employee` names the record by that argument, and
the tool table copies the same argument into `context.input`, so the
employee a write is for and the record it changes are one value. The
policies compare it with the caller. In orders a write names a
customer and an order separately, and the Orders API must refuse an
order the customer does not own; here the HR API has no such check to
make. A read is decided on the response, on the record the API
returned, by comparing the record's `employeeId` and `manager` with
the caller.

## Who reads and writes each field

The contract gives every field a level and a writer. The policies
grant levels and writers; no policy names a field.

| Field | Level | Writer | alice, own record | bob, alice's record | maya, alice's manager | hana of HR, alice's record |
|---|---|---|---|---|---|---|
| employeeId, workEmail | public | system | reads | reads | reads | reads |
| name, jobTitle, department, manager | public | hr | reads | reads | reads | reads, writes |
| homeAddress.*, personalPhone | confidential | owner | reads, writes | none | none | reads |
| salary | confidential | system | reads | none | reads | reads |
| hrNotes | internal | hr | none | none | none | reads, writes |
| bankAccount | restricted | system | none | none | none | none |

A colleague's view is the directory. HR does not set an employee's
address in direct mode: an address change is always the employee's,
made by them or by HR or the assistant for them. Nobody reads the bank
account, and nobody changes it, the salary, the work email, or the id
through these tools, so a call that changes the address and the salary
together is refused whole and names the salary.

The payload round decides every leaf a call names, changed or not. An
agent that sends the whole address sends six leaves, all the
employee's. An address sent as one string names no leaf of the
contract and is refused.

## A manager reads a report's pay and not their address

The record names the employee's manager, a public field HR sets, typed
`User` like the id. On the response leg a manager reads a direct
report's directory fields and the confidential fields the report does
not set themself, which is the salary. The home address and the
personal phone are confidential too, but their writer is `owner`: the
report sets them, and they stay the report's and HR's. The policy
reads both of the contract's tag maps, the level and the writer, and
names no field.

A manager changes nothing on a report's record through these tools. A
write is decided before the API is called, when the interceptor does
not have the record and so cannot know who its manager is.

## HR acting for an employee

When alice tells HR about a move, hana changes the address with a
token exchanged for alice: the subject is alice and the actor is hana.
Every grant but HR's writes is written for the person on the call, the
acted-for one when there is one, so hana holds alice's grants and
reads no HR notes while acting. HR's writes require direct mode, so
while acting hana sets no title. Only HR and the HR assistant act for
an employee: a token in which alice acts for bob is refused whatever
it asks.

## The HR assistant on a call

The HR assistant is an agent with a workload token of its own. When
alice talks with it, it holds a token exchanged for alice, with alice
as the subject and the assistant as the actor, and the projection
makes the assistant the principal, typed `Agent`, and alice
`context.actingFor`, as in reservations. The assistant holds the
grants of the person it talks with: for alice it reads alice's record,
the directory, and changes alice's address; for maya it reads maya's
reports' pay.

For an HR partner it reads what HR reads, and changes only what an
employee may change about themself. A title, a department, a manager,
or a note is set by an HR partner calling the tools directly. Alone,
with no one to act for, the assistant reads, lists, and changes
nothing. Any other agent acting for an employee is refused.

Cedar's strict validator will not join `User` and `Agent` in one
if-then-else, so the person on the call is written as two branches,
`(context has actingFor && x == context.actingFor) || (!(context has
actingFor) && x == principal)`, wherever a policy needs it.

## The directory list

`hr___list_employees` lists every employee. Any employee may list; the
response leg then decides each row and its fields as for one record,
so one list shows each row as its reader may see it. Alice's list has
alice's own row with the address and the salary, and everyone else's
directory fields. Maya's has the rows of maya's reports with their
salary, maya's own row in full, and hana's directory fields.

## The guardrails

Each file under `guardrails/` is one sentence of an HR data policy,
proven to change no decision the policies make:

- the home address and the personal phone are set only on the record
  of the person on the call (`owner-fields-only-on-own-record`)
- a home address, a personal phone, or a salary is read only by its
  employee, their manager, or HR
  (`confidential-only-to-the-employee-their-manager-and-hr`), and the
  ones the employee sets, the address and the phone, only by the
  employee or HR (`personal-fields-only-to-the-employee-and-hr`)
- HR's notes are read only when an HR partner is the person on the
  call (`internal-only-to-hr`)
- while acting, HR or the assistant writes only for the person acted
  for, and only that person's own fields
  (`acting-writes-bounded-by-employee`,
  `acting-writes-owner-fields-only`)
- only HR and the HR assistant act for an employee
  (`only-hr-and-the-assistant-act-for-employees`), and an agent alone
  reads, lists, and changes nothing
  (`the-assistant-alone-is-granted-nothing`)
- nobody reads the bank account (`restricted-unreadable`), and nobody
  sets a system field (`system-fields-unwritable`)
- a field the contract does not declare is never read or set
  (`fail-closed`, `mass-assignment-fail-closed`)

## Running it

```sh
uv run cedar-odcs check usecases/hr
uv run cedar-odcs check-access usecases/hr --caller usecases/hr/tests/identities/alice.json
uv run cedar-odcs dry-run usecases/hr --caller usecases/hr/tests/identities/bob.json --tool hr___get_employee --arg employeeId=alice --response usecases/hr/tests/responses/alice.json
uv run cedar-odcs dry-run usecases/hr --caller usecases/hr/tests/identities/alice.json --tool hr___update_employee --arg employeeId=alice --arg 'changes={"homeAddress": {"line1": "48 Pine St"}, "salary": 250000}'
uv run cedar-odcs dry-run usecases/hr --caller usecases/hr/tests/identities/maya.json --tool hr___list_employees --response usecases/hr/tests/lists/employees.json
uv run cedar-odcs dry-run usecases/hr --caller usecases/hr/tests/identities/alice-through-assistant.json --tool hr___update_employee --arg employeeId=alice --arg 'changes={"homeAddress": {"line1": "48 Pine St"}}'
```

The first builds, validates, runs the test cases, and proves the
guardrails. The second lists what alice may read and write. The third
is bob reading alice's record, which returns the directory fields. The
fourth is alice changing their address and their salary in one call,
refused for the salary. The fifth is maya listing the directory: the
rows of maya's reports carry their salary and no address. The sixth is the
assistant changing alice's address for them.
