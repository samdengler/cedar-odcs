// HR: an employee updates their own home address, colleagues see the
// directory, a manager sees their reports' pay, and HR keeps the rest.
//
// The record is the employee. Its id, employeeId, is the employee's
// own user id, the token's subject, and the record carries it as an
// attribute typed User, with the employee's manager beside it. A read
// is decided on the record the API returned, so the read policies
// compare resource.employeeId and resource.manager. A write is decided
// before the API is called and never has the record, so the write
// policies compare the employee the call names,
// context.input.employeeId. That argument is also the id of the record
// the call writes (usecase.py): the employee a write names and the
// record it changes are one value, and the HR API has no ownership
// check of its own to make.
//
// Three ways onto a call. An employee or an HR partner calls the tools
// directly and is the principal, a User. An HR partner acts for an
// employee with a token exchanged for them: the HR partner is the
// principal and the employee is context.actingFor. Or the HR
// assistant holds the token for the person talking with it: the
// assistant is the principal, an Agent, and the person is
// context.actingFor.
//
// "The person on the call" is context.actingFor when there is one,
// else the principal. The self-service, directory, manager, and HR
// read policies are written for that person, so HR acting for alice
// holds alice's grants, and the assistant holds the grants of whoever
// it talks with. Cedar's strict validator will not join User and Agent
// in one if-then-else, so the person is written as two branches:
//
//   (context has actingFor && <x> == context.actingFor) ||
//   (!(context has actingFor) && <x> == principal)
//
// HR's writes are direct only. A title, a department, or a note is set
// by an HR partner calling the tools, never while acting for someone
// and never through the assistant. An address change is always the
// employee's: made by them, or by HR or the assistant for them.
//
// No policy names a field. The levels and writers are the contract's
// (contract/employee.odcs.yaml).

// policy0: Any employee reads any employee record; the field policies
// decide what of it.
@id("employee-reads-any-record")
permit(
  principal,
  action == Action::"ReadEmployee",
  resource
) when {
  (context has actingFor && context.actingFor in Role::"employee") ||
  (!(context has actingFor) && principal in Role::"employee")
};

// policy1: An employee reads the public and confidential fields of
// their own record: their home address and salary among them.
@id("employee-reads-own-fields")
permit(
  principal,
  action == Action::"ReadEmployeeField",
  resource
) when {
  resource has employeeId &&
  ((context has actingFor && resource.employeeId == context.actingFor) ||
   (!(context has actingFor) && resource.employeeId == principal)) &&
  context has field &&
  Contract::"Employee".hasTag(context.field) &&
  ["public", "confidential"].contains(Contract::"Employee".getTag(context.field))
};

// policy2: Any employee reads the public fields of any record: the
// directory, a name, a title, a department, a manager, a work email.
@id("employee-reads-directory-fields")
permit(
  principal,
  action == Action::"ReadEmployeeField",
  resource
) when {
  ((context has actingFor && context.actingFor in Role::"employee") ||
   (!(context has actingFor) && principal in Role::"employee")) &&
  context has field &&
  Contract::"Employee".hasTag(context.field) &&
  Contract::"Employee".getTag(context.field) == "public"
};

// policy3: A manager reads the confidential fields of a direct
// report's record that the report does not set: the salary. The home
// address and the personal phone are the ones the report sets, their
// own, and a manager reads neither.
@id("manager-reads-direct-report-fields")
permit(
  principal,
  action == Action::"ReadEmployeeField",
  resource
) when {
  resource has manager &&
  ((context has actingFor && resource.manager == context.actingFor) ||
   (!(context has actingFor) && resource.manager == principal)) &&
  context has field &&
  Contract::"Employee".hasTag(context.field) &&
  Contract::"Employee".getTag(context.field) == "confidential" &&
  Contract::"Employee/writers".hasTag(context.field) &&
  Contract::"Employee/writers".getTag(context.field) != "owner"
};

// policy4: An employee updates their own record. The call names the
// employee, and the record it writes is that employee's.
@id("employee-updates-own-record")
permit(
  principal,
  action == Action::"UpdateEmployee",
  resource
) when {
  context has input &&
  context.input has employeeId &&
  ((context has actingFor && context.input.employeeId == context.actingFor) ||
   (!(context has actingFor) && context.input.employeeId == principal))
};

// policy5: An employee sets the fields whose writer is "owner" on their
// own record: the home address and the personal phone.
@id("employee-updates-own-fields")
permit(
  principal,
  action == Action::"UpdateEmployeeField",
  resource
) when {
  context has input &&
  context.input has employeeId &&
  ((context has actingFor && context.input.employeeId == context.actingFor) ||
   (!(context has actingFor) && context.input.employeeId == principal)) &&
  context has field &&
  Contract::"Employee/writers".hasTag(context.field) &&
  Contract::"Employee/writers".getTag(context.field) == "owner"
};

// policy6: HR reads the public, internal, and confidential fields of
// any record, when an HR partner is the person on the call: directly or
// through the assistant. HR acting for an employee holds the
// employee's grants. Restricted fields stay nobody's.
@id("hr-reads-fields-on-any-record")
permit(
  principal,
  action == Action::"ReadEmployeeField",
  resource
) when {
  ((context has actingFor && context.actingFor in Role::"hr") ||
   (!(context has actingFor) && principal in Role::"hr")) &&
  context has field &&
  Contract::"Employee".hasTag(context.field) &&
  ["public", "internal", "confidential"].contains(Contract::"Employee".getTag(context.field))
};

// policy7: HR updates any record at object level, in direct mode;
// policy8 bounds the fields.
@id("hr-updates-any-record")
permit(
  principal in Role::"hr",
  action == Action::"UpdateEmployee",
  resource
) when {
  !(context has actingFor)
};

// policy8: HR sets the fields whose writer is "hr", on any record, in
// direct mode: the name, the title, the department, the manager, and
// its own notes. An employee's home address is not HR's to set; HR
// sets it by acting for the employee.
@id("hr-updates-hr-fields")
permit(
  principal in Role::"hr",
  action == Action::"UpdateEmployeeField",
  resource
) when {
  !(context has actingFor) &&
  context has field &&
  Contract::"Employee/writers".hasTag(context.field) &&
  Contract::"Employee/writers".getTag(context.field) == "hr"
};

// policy9: Anyone may look up a record; the response decides.
@id("anyone-looks-up-a-record")
permit(
  principal,
  action == Action::"LookupEmployee",
  resource
);

// policy10: Any employee lists the directory. The response leg decides
// each row and its fields as for one record, so the list shows a
// reader's own row, a report's, and a colleague's each as that reader
// may see it.
@id("employee-lists-the-directory")
permit(
  principal,
  action == Action::"ListEmployees",
  resource == Collection::"employees"
) when {
  (context has actingFor && context.actingFor in Role::"employee") ||
  (!(context has actingFor) && principal in Role::"employee")
};

// policy11: Only HR and the HR assistant act for an employee. Every
// caller here is an employee, so a token in which one employee acts
// for another, alice for bob say, matches this forbid and nothing else
// matters; so does a token from any agent but the HR assistant.
@id("only-hr-and-the-assistant-act-for-employees")
forbid(
  principal,
  action,
  resource
) when {
  context has actingFor &&
  !(principal in Role::"hr") &&
  !(principal == Agent::"hr-assistant")
};
