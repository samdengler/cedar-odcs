"""cedar-odcs: the mechanism at the command line.

    cedar-odcs run-tests    usecases/reservations
    cedar-odcs authorize    usecases/reservations --principal 'User::"sam"' \\
                              --action 'Action::"ReadReservation"' --resource 'Reservation::"ABC123"'
    cedar-odcs dry-run      usecases/reservations --caller sam.json \\
                              --tool reservations___get_reservation --arg recordLocator=XYZ789 \\
                              --response record.json
    cedar-odcs check-access usecases/reservations --caller agent.json \\
                              --presented locator=ABC123 --presented lastName=SMITH
    cedar-odcs share        usecases/reservations --case "co-traveler"
    cedar-odcs pull         usecases/reservations
    cedar-odcs build        usecases/reservations
    cedar-odcs tools        usecases/reservations
    cedar-odcs validate     usecases/reservations
    cedar-odcs prove        usecases/reservations
    cedar-odcs check        usecases/reservations

Verbs match the official cedar command where the meaning is the same
(authorize, validate, run-tests, new) and add the two ideas Cedar has
no word for: a dry run of one tool call through both legs, and a
report of what an identity may do. pull writes the ODCS contract from
the catalog, for a use case that has one; build reads the contract and
writes the Cedar files; tools compares each tool's outputSchema in
tools.json with the contract's leaves. check runs pull where there is
a catalog, then build, tools where there is a tools.json, validate,
run-tests, and prove in order and stops at the first
failure; each stays callable on its own. Files are Cedar's own formats:
policies.cedar, entities.json, .cedarschema, the corpus in the
cedar-integration-tests form.

A use case is a directory with usecase.py; every command takes it as
its first argument, or runs in the current directory.
"""

import argparse
import base64
import gzip
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import cedarpy

from cedar_odcs.engine import calls
from cedar_odcs.engine.corpus import case_files, name_of, policy_names, run_case
from cedar_odcs.engine.enforce import Engine, explain
from cedar_odcs.engine.usecase import paths, policies_text

REPO = Path(__file__).resolve().parents[2]


class Usage(Exception):
    pass


# ---------------------------------------------------------------- loading

def load_use_case(directory: str):
    root = Path(directory).resolve()
    module_path = root / "usecase.py"
    if not module_path.exists():
        raise Usage(f"{root} has no usecase.py; a use case directory is needed")
    spec = importlib.util.spec_from_file_location(f"usecase_{root.name}", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _ref(value):
    if isinstance(value, dict):
        return f'{value["type"]}::"{value["id"]}"'
    return value


def _parse_value(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return text


def _pairs(items) -> dict:
    out = {}
    for item in items or []:
        if "=" not in item:
            raise Usage(f"expected key=value, got {item!r}")
        key, value = item.split("=", 1)
        out[key] = _parse_value(value)
    return out


def _identity(path: str) -> dict:
    """An identity file: the claims of one caller's credential, the JWT
    the Gateway verified, as one JSON object with at least a sub."""
    claims = json.loads(Path(path).read_text())
    if not isinstance(claims, dict) or "sub" not in claims:
        raise Usage(f"{path} is not an identity file: a JSON object of claims with a sub")
    return claims


def _schema_text(use_case) -> str:
    generated = paths(use_case.root).generated
    files = sorted(generated.glob("*.cedarschema")) if generated.exists() else []
    files = [f for f in files if f.name != "entities.cedarschema"]
    if not files:
        raise Usage(f"{use_case.root} has no generated schema; run build first")
    return files[0].read_text()


def _actions(schema: str) -> list:
    """[(action name, resource type)] from a Cedar schema."""
    out = []
    for m in re.finditer(r"action\s+(\w+)\s+appliesTo\s*\{(.*?)\n\};", schema, re.S):
        resource = re.search(r"resource:\s*\[([^\]]*)\]", m.group(2))
        out.append((m.group(1), resource.group(1).strip() if resource else ""))
    return out


# ---------------------------------------------------------------- run-tests

def cmd_run_tests(args):
    module = load_use_case(args.directory)
    root = module.USE_CASE.root
    failures = total = 0
    exported = []
    for spec_file in case_files(root):
        spec = json.loads(spec_file.read_text())
        policies = policies_text(root, spec["policies"])
        entities = (root / spec["entities"]).read_text()
        names = policy_names(policies)
        print(f"\n{spec_file.relative_to(root)}")
        for case in spec["requests"]:
            total += 1
            outcome = run_case(policies, entities, case)
            if outcome.ok:
                print(f"  PASS  {case['description']}")
            else:
                failures += 1
                print(f"  FAIL  {case['description']}")
                print(f"        expected {case['decision']} by {case.get('reason') or 'no policy'}, "
                      f"got {outcome.actual} by "
                      f"{[name_of(r, names) for r in outcome.reasons] or 'no policy'}")
                print(f"        {_ref(case['principal'])} {_ref(case['action'])} {_ref(case['resource'])} "
                      f"{json.dumps(case.get('context', {}))}")
                for error in outcome.result.diagnostics.errors:
                    print(f"        error: {error}")
            exported.append({
                "name": case["description"],
                "request": {"principal": case["principal"], "action": case["action"],
                            "resource": case["resource"], "context": case.get("context", {})},
                "entities": json.loads(entities),
                "decision": case["decision"].lower(),
                "reason": outcome.expected_reasons,
                "num_errors": len(outcome.expected_errors),
            })
    print(f"\n{total - failures} passed, {failures} failed")
    if args.cedar_tests:
        Path(args.cedar_tests).write_text(json.dumps(exported, indent=2) + "\n")
        print(f"wrote {len(exported)} cases in the cedar run-tests format to {args.cedar_tests}")
    return 1 if failures else 0


# ---------------------------------------------------------------- authorize

def cmd_authorize(args):
    module = load_use_case(args.directory)
    use_case = module.USE_CASE
    if args.request_json:
        spec = json.loads(Path(args.request_json).read_text())
        request = {k: _ref(spec[k]) for k in ("principal", "action", "resource")}
        request["context"] = spec.get("context", {})
    else:
        missing = [f for f in ("principal", "action", "resource") if getattr(args, f) is None]
        if missing:
            raise Usage(f"--{', --'.join(missing)} needed, or --request-json")
        request = {"principal": args.principal, "action": args.action, "resource": args.resource,
                   "context": json.loads(args.context) if args.context else {}}
    policies = use_case.policies
    names = policy_names(policies)
    result = cedarpy.is_authorized(request, policies, json.dumps(use_case.entities))
    decision = "Allow" if result.decision == cedarpy.Decision.Allow else "Deny"
    print(f"{decision}  {request['principal']} {request['action']} {request['resource']}")
    if request["context"]:
        print(f"       context {json.dumps(request['context'])}")
    if result.diagnostics.reasons:
        for r in sorted(result.diagnostics.reasons):
            print(f"       by {name_of(r, names)}")
    else:
        print("       no policy matched: the default deny")
    for error in result.diagnostics.errors:
        print(f"       error: {error}")
    return 0


# ---------------------------------------------------------------- dry-run

def cmd_dry_run(args):
    module = load_use_case(args.directory)
    use_case = module.USE_CASE
    claims = _identity(args.caller)
    tool = use_case.tools.get(args.tool)
    if tool is None:
        raise Usage(f"tool {args.tool} is not in the use case's tool table: {', '.join(use_case.tools)}")
    arguments = _pairs(args.arg)
    engine = Engine(use_case)
    projection = engine.projection(claims)
    print(f"Identity   {projection.principal}, {projection.mode}"
          + (f", acting for {projection.context['actingFor']['__entity']['id']}" if projection.context else ""))
    print(f"Tool       {args.tool}  {json.dumps(arguments)}")
    # A call the engine cannot make sense of is rejected in the same
    # words the interceptor rejects it with.
    try:
        governed = calls.call(use_case, args.tool, arguments)
        decision = engine.decide_request(claims, governed)
    except (ValueError, KeyError, TypeError) as e:
        print(f"Request    rejected: request could not be evaluated: {e}")
        return 1
    if not decision.allowed:
        print(f"Request    rejected: {explain(governed, decision)}")
        return 1
    print("Request    forwarded: the verb round passed"
          + (" and the payload round passed" if governed.payload is not None else ""))
    if not args.response:
        print("Response   (give --response FILE to run the response leg on a payload)")
        return 0
    payload = json.loads(Path(args.response).read_text())
    if governed.returns == "list":
        if not isinstance(payload, list):
            raise Usage("a list tool's response must be a JSON array")
    elif not isinstance(payload, dict):
        raise Usage("an object tool's response must be a JSON object")
    decision = engine.decide_response(claims, governed, payload)
    for d in decision.dropped:
        print(f"Response   row {d['position']} ({d['id'] or 'no id'}) dropped: {d['reason']}")
    for position, paths in decision.stripped.items():
        print(f"Response   row {position} stripped: {', '.join(paths)}")
    if not decision.dropped and not decision.stripped:
        print("Response   nothing removed")
    result = decision.rows if governed.returns == "list" else (decision.rows[0] if decision.rows else {})
    print("Returned   " + json.dumps(result, indent=2).replace("\n", "\n           "))
    return 0


# ---------------------------------------------------------------- check-access

def cmd_check_access(args):
    module = load_use_case(args.directory)
    use_case = module.USE_CASE
    claims = _identity(args.caller)
    engine = Engine(use_case)
    projection = engine.projection(claims)
    context = {}
    presented = _pairs(args.presented)
    if presented:
        context["presented"] = {k: v.upper() if isinstance(v, str) else v for k, v in presented.items()}
    if args.record:
        record = json.loads(Path(args.record).read_text())
        entity = engine.entity_from_row(record)
    else:
        stored = [e for e in use_case.entities if e["uid"]["type"] == use_case.resource_type]
        entity = stored[0] if stored else {"uid": {"type": use_case.resource_type, "id": "unknown"}, "attrs": {}, "parents": []}
    resource = f'{entity["uid"]["type"]}::"{entity["uid"]["id"]}"'
    line = f"Access of {projection.principal} ({projection.mode})"
    if projection.context:
        line += f", acting for {projection.context['actingFor']['__entity']['id']}"
    if presented:
        line += f", presenting {json.dumps(context['presented'])}"
    print(line)
    print(f"On {resource} with attributes {json.dumps(entity['attrs'])}\n")

    schema = _schema_text(use_case)
    collections = [t["collection"] for t in use_case.tools.values() if "collection" in t]
    held, not_held = [], []
    field_verbs = {use_case.read_field_action, *use_case.field_actions.values()}
    for action, resource_type in _actions(schema):
        if f'Action::"{action}"' in field_verbs:
            continue  # the field rounds are reported by path below
        if resource_type == use_case.resource_type:
            target = resource
        elif resource_type == "Collection" and collections:
            target = f'Collection::"{collections[0]}"'
        else:
            target = f'{resource_type}::"?"'
        allowed = engine.is_allowed(projection, f'Action::"{action}"', target, context, [entity])
        (held if allowed else not_held).append(action)
    print(f"Verbs held      {', '.join(held) or 'none'}")
    print(f"Verbs not held  {', '.join(not_held) or 'none'}\n")

    maps = {e["uid"]["id"]: e["tags"] for e in use_case.entities if e["uid"]["type"] == "Contract"}
    levels = maps.get(use_case.resource_type, {})
    writers = maps.get(f"{use_case.resource_type}/writers", {})
    readable, unreadable = [], []
    for path, level in levels.items():
        ok = engine.is_allowed(projection, use_case.read_field_action, resource, {**context, "field": path}, [entity])
        (readable if ok else unreadable).append(f"{path} ({level})")
    print(f"Readable        {', '.join(readable) or 'nothing'}")
    print(f"Not readable    {', '.join(unreadable) or 'nothing'}\n")
    write_action = next(iter(use_case.field_actions.values()), None)
    if write_action:
        writable, unwritable = [], []
        for path, writer in writers.items():
            ok = engine.is_allowed(projection, write_action, resource, {**context, "field": path}, [entity])
            (writable if ok else unwritable).append(f"{path} ({writer})")
        print(f"Writable        {', '.join(writable) or 'nothing'}")
        print(f"Not writable    {', '.join(unwritable) or 'nothing'}")
    return 0


# ---------------------------------------------------------------- share

PLAYGROUND = "https://www.cedarpolicy.com/en/playground"


def playground_link(policy: str, schema: str, entities: str, request: dict) -> str:
    """A pre-filled link to Cedar's playground.

    The playground's share button encodes its state as gzipped,
    base64 JSON in the URL fragment after 'data:' (interface version
    1: policy, schema, entities, and context as strings, the three
    parties as {type, id}). The format is read from the site's source,
    src/playground-helpers/playgroundExportHelpers.ts, and is not
    documented; if the playground changes it, this link stops working
    and nothing else does.
    """
    def identifier(ref: str) -> dict:
        entity_type, _, entity_id = ref.partition("::")
        return {"type": entity_type, "id": entity_id.strip('"')}

    state = {
        "interfaceVersion": 1,
        "cedarVersion": "4.0.0",
        "playgroundData": {
            "policy": policy,
            "schema": schema,
            "principal": identifier(request["principal"]),
            "action": identifier(request["action"]),
            "resource": identifier(request["resource"]),
            "entities": json.dumps(json.loads(entities), separators=(",", ":")),
            "context": json.dumps(request.get("context", {}), separators=(",", ":")),
            "isAVPFormat": False,
        },
    }
    raw = json.dumps(state, separators=(",", ":")).encode()
    blob = base64.b64encode(gzip.compress(raw)).decode()
    return f"{PLAYGROUND}#data:{blob}"


def cmd_share(args):
    module = load_use_case(args.directory)
    use_case = module.USE_CASE
    root = use_case.root
    if args.request_json:
        spec = json.loads(Path(args.request_json).read_text())
        request = {k: _ref(spec[k]) for k in ("principal", "action", "resource")}
        request["context"] = spec.get("context", {})
        label = args.request_json
    elif args.case:
        found = []
        for spec_file in case_files(root):
            for case in json.loads(spec_file.read_text())["requests"]:
                if args.case.lower() in case["description"].lower():
                    found.append(case)
        if not found:
            raise Usage(f"no corpus case mentions {args.case!r}")
        if len(found) > 1:
            print(f"{len(found)} cases match; using the first:", file=sys.stderr)
        case = found[0]
        request = {k: _ref(case[k]) for k in ("principal", "action", "resource")}
        request["context"] = case.get("context", {})
        label = case["description"]
    else:
        raise Usage("--case TEXT or --request-json FILE")
    link = playground_link(use_case.policies, _schema_text(use_case),
                           json.dumps(use_case.entities, indent=2), request)
    print(label)
    print(link)
    return 0


# ---------------------------------------------------------------- build, validate, prove

def cmd_pull(args):
    """Stage one: the catalog's answers to the ODCS contract. Only a use
    case with a PULL descriptor has a catalog; the others write the
    contract by hand."""
    module = load_use_case(args.directory)
    source = getattr(module, "PULL", None)
    if source is None:
        raise Usage(f"{args.directory} names no catalog source (no PULL in usecase.py); its contract is written by hand")
    from cedar_odcs.engine.contract import pull, write
    outputs = pull(module.USE_CASE.root, module.CONTRACT, **source)
    write(module.USE_CASE.root, outputs)
    for rel in outputs:
        print("wrote", rel)
    return 0


def cmd_build(args):
    """Stage two: the committed ODCS contract to the Cedar files."""
    module = load_use_case(args.directory)
    from cedar_odcs.engine.contract import ContractError, build, write
    try:
        write_actions = list(module.USE_CASE.field_actions.values())
        outputs = build(module.USE_CASE.root, module.CONTRACT, module.USE_CASE.read_field_action,
                        write_actions[0] if write_actions else None)
    except ContractError as e:
        raise Usage(f"the contract does not build: {e}") from e
    write(module.USE_CASE.root, outputs)
    for rel in outputs:
        print("wrote", rel)
    return 0


def cmd_validate(args):
    """The policies against the built schema: the official cedar command
    when it is on the path, otherwise cedarpy.validate_policies, which the
    installed binding already provides. A missing cedar is not a failure;
    say which validator ran either way."""
    module = load_use_case(args.directory)
    use_case = module.USE_CASE
    generated = paths(use_case.root).generated
    schema_files = [f for f in sorted(generated.glob("*.cedarschema")) if f.name != "entities.cedarschema"]
    if not schema_files:
        raise Usage("no generated schema; run build first")
    schema_file = schema_files[0]
    policies = use_case.policies  # policies.cedar and any rendered grants
    cedar = shutil.which("cedar")
    if cedar is not None:
        import tempfile
        print(f"validator  cedar ({cedar})")
        sys.stdout.flush()
        with tempfile.NamedTemporaryFile("w", suffix=".cedar") as policies_file:
            policies_file.write(policies)
            policies_file.flush()
            return subprocess.call([cedar, "validate", "--schema", str(schema_file),
                                    "--policies", policies_file.name])
    print("validator  cedarpy.validate_policies (the cedar command is not on the path; "
          "optional: `cargo install cedar-policy-cli` switches to the official validator)")
    result = cedarpy.validate_policies(policies, schema_file.read_text())
    if not result.validation_passed:
        for error in result.errors:
            print(f"error: {error}")
        return 1
    print("validation passed")
    return 0


def _analysis() -> Path:
    """The analysis crate: $CEDAR_ODCS_ANALYSIS, else analysis/ in this
    checkout. An installed cedar-odcs has no crate beside it; a use case
    outside this repository points the variable at a checkout's."""
    return Path(os.environ.get("CEDAR_ODCS_ANALYSIS") or REPO / "analysis").resolve()


def _missing_cvc5() -> bool:
    """Whether cvc5 is unreachable, checked the same way analysis/src/main.rs's
    solver() finds it: $CVC5, the bundled copy, then PATH."""
    if os.environ.get("CVC5"):
        return False
    bundled = _analysis() / ".tools/cvc5-macOS-arm64-static/bin/cvc5"
    if bundled.exists():
        return False
    return shutil.which("cvc5") is None


def cmd_prove(args):
    """`prove DIR` proves one use case (`cargo run -- prove DIR`); `prove`
    with no directory, or with the repository root, proves the history
    chain instead (`cargo run -- prove-history`). Needs cargo and cvc5;
    when either is missing, say so and exit 2. The crate is found by
    _analysis()."""
    analysis = _analysis()
    if not (analysis / "Cargo.toml").is_file():
        print(f"the analysis crate is not at {analysis}. prove needs a cedar-odcs checkout;"
              " set CEDAR_ODCS_ANALYSIS to its analysis/ directory.")
        return 2
    if shutil.which("cargo") is None:
        print("cargo is not installed. The proofs need Rust and the cvc5 solver; see analysis/README.md (Running).")
        return 2
    if _missing_cvc5():
        print("cvc5 is not installed. See analysis/README.md (Running):")
        print("    curl -sL -o cvc5.zip https://github.com/cvc5/cvc5/releases/download/cvc5-1.3.1/cvc5-macOS-arm64-static.zip")
        print("    unzip -q cvc5.zip -d analysis/.tools && rm cvc5.zip")
        print("    chmod +x analysis/.tools/cvc5-macOS-arm64-static/bin/cvc5")
        return 2
    directory = Path(getattr(args, "directory", ".")).resolve()
    sys.stdout.flush()
    if directory == REPO:
        return subprocess.call(["cargo", "run", "--quiet", "--", "prove-history", str(REPO)], cwd=analysis)
    return subprocess.call(["cargo", "run", "--quiet", "--", "prove", str(directory)], cwd=analysis)


def cmd_check(args):
    """pull where the use case has a catalog, then build, the tool schema
    gate where there is a tools.json, validate, run-tests, prove, in order, stopping at the first failure; a
    one-line heading per step, then the step's own output, then one
    ok/failed line per step that ran. --skip pull keeps a hand-edited
    contract from being rewritten by the catalog; --skip prove is for a
    pipeline with no cargo or cvc5, which runs prove on its own."""
    directory = args.directory
    root = Path(directory).resolve()
    skip = set(getattr(args, "skip", None) or [])
    results = []
    rc = 0

    if getattr(load_use_case(directory), "PULL", None) is not None and "pull" not in skip:
        print("== pull ==")
        rc = cmd_pull(args)
        results.append(("pull", rc == 0))
        print()

    if rc == 0:
        print("== build ==")
        rc = cmd_build(args)
    if rc == 0:
        generated = [str(root / "contract"), str(root / "entities.json")]
        tracked = subprocess.run(["git", "ls-files", "--", *generated], cwd=root,
                                 capture_output=True, text=True)
        if tracked.returncode != 0 or not tracked.stdout.strip():
            print(f"generated files under {directory} are not committed; nothing to compare")
        elif subprocess.call(["git", "diff", "--quiet", "--", *generated], cwd=root) != 0:
            print(f"generated files under {directory} changed: the committed artifacts were behind their sources")
        else:
            print(f"generated files under {directory} unchanged")
    results.append(("build", rc == 0))

    if rc == 0 and (root / "tools.json").is_file():
        print("\n== tools ==")
        rc = cmd_tools(args)
        results.append(("tools", rc == 0))

    if rc == 0:
        print("\n== validate ==")
        rc = cmd_validate(args)
        results.append(("validate", rc == 0))

    if rc == 0:
        print("\n== run-tests ==")
        rc = cmd_run_tests(argparse.Namespace(directory=directory, cedar_tests=None))
        results.append(("run-tests", rc == 0))

    if rc == 0 and "prove" not in skip:
        print("\n== prove ==")
        rc = cmd_prove(args)
        results.append(("prove", rc == 0))

    print()
    for name, ok in results:
        print(f"{name}: {'ok' if ok else 'failed'}")
    for name in sorted(skip):
        print(f"{name}: skipped")
    return 0 if all(ok for _, ok in results) else 1


def tool_schema_differences(module) -> list:
    """For a use case with tools.json beside usecase.py: every governed
    tool that returns an object or a list must name in its outputSchema
    exactly the contract's leaves. [(tool, only in outputSchema, only in
    the contract)] for each tool that differs."""
    from cedar_odcs.engine.contract import leaf_paths, output_schema_paths
    root = module.USE_CASE.root
    leaves = leaf_paths(root, module.CONTRACT)
    schemas = {t["name"]: t for t in json.loads((root / "tools.json").read_text())}
    out = []
    for name, tool in module.USE_CASE.tools.items():
        if tool.get("returns") not in ("object", "list"):
            continue
        schema = schemas.get(name.split("___", 1)[-1], schemas.get(name))
        if schema is None or "outputSchema" not in schema:
            out.append((name, [], sorted(leaves)))
            continue
        paths_ = output_schema_paths(schema["outputSchema"])
        if paths_ != leaves:
            out.append((name, sorted(paths_ - leaves), sorted(leaves - paths_)))
    return out


def cmd_tools(args):
    """The tool schema gate: each tool's outputSchema in tools.json against
    the contract's leaves."""
    module = load_use_case(args.directory)
    differences = tool_schema_differences(module)
    for name, schema_only, contract_only in differences:
        print(f"{name}: outputSchema and the contract differ")
        print(f"  in outputSchema, not in the contract: {', '.join(schema_only) or '(none)'}")
        print(f"  in the contract, not in outputSchema: {', '.join(contract_only) or '(none)'}")
    if not differences:
        print("every outputSchema in tools.json names the contract's leaves")
    return 1 if differences else 0


def cmd_new(args):
    raise Usage("new is planned; copy usecases/reservations for now and edit usecase.py")


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cedar-odcs", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def with_dir(p):
        p.add_argument("directory", nargs="?", default=".", help="a use case directory (default: .)")
        return p

    p = with_dir(sub.add_parser("run-tests", help="run the corpus and report every case"))
    p.add_argument("--cedar-tests", metavar="FILE", help="also write the cases in the cedar run-tests format")
    p.set_defaults(func=cmd_run_tests)

    p = with_dir(sub.add_parser("authorize", help="one Cedar request, with the policy that decided it"))
    p.add_argument("--principal"); p.add_argument("--action"); p.add_argument("--resource")
    p.add_argument("--context", help="JSON")
    p.add_argument("--request-json", metavar="FILE")
    p.set_defaults(func=cmd_authorize)

    p = with_dir(sub.add_parser("dry-run", help="one tool call through both legs, without calling the tool"))
    p.add_argument("--caller", required=True, metavar="FILE", help="an identity file: the claims of one caller's credential")
    p.add_argument("--tool", required=True, help="an MCP tool name from the use case's tool table")
    p.add_argument("--arg", action="append", metavar="KEY=VALUE", help="a tool argument (JSON values allowed)")
    p.add_argument("--response", metavar="FILE", help="the tool's response payload, to run the response leg")
    p.set_defaults(func=cmd_dry_run)

    p = with_dir(sub.add_parser("check-access", help="what an identity may do: verbs, readable paths, writable paths"))
    p.add_argument("--caller", required=True, metavar="FILE", help="an identity file: the claims of one caller's credential")
    p.add_argument("--presented", action="append", metavar="KEY=VALUE", help="a presented fact, e.g. lastName=SMITH")
    p.add_argument("--record", metavar="FILE", help="a payload row to decide on (default: the first stored one)")
    p.set_defaults(func=cmd_check_access)

    p = with_dir(sub.add_parser("share", help="a pre-filled link to Cedar's playground"))
    p.add_argument("--case", help="text from a corpus case's description")
    p.add_argument("--request-json", metavar="FILE")
    p.set_defaults(func=cmd_share)

    with_dir(sub.add_parser("pull", help="the catalog to the ODCS contract, for a use case with a catalog source")).set_defaults(func=cmd_pull)
    with_dir(sub.add_parser("build", help="the ODCS contract to Cedar: the tag maps, the schema, entities.json")).set_defaults(func=cmd_build)
    with_dir(sub.add_parser("tools", help="each outputSchema in tools.json against the contract's leaves")).set_defaults(func=cmd_tools)
    with_dir(sub.add_parser("validate", help="policies against the built schema, with cedar or cedarpy")).set_defaults(func=cmd_validate)
    with_dir(sub.add_parser("prove", help="the symbolic proofs, with cargo and cvc5 (no directory, or the repository root: the history chain)")).set_defaults(func=cmd_prove)
    p = with_dir(sub.add_parser("check", help="pull (with a catalog), build, validate, run-tests, prove, in order, stopping at the first failure"))
    p.add_argument("--skip", action="append", choices=["pull", "prove"], help="leave out a step (repeatable)")
    p.set_defaults(func=cmd_check)
    with_dir(sub.add_parser("new", help="scaffold a use case (planned)")).set_defaults(func=cmd_new)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Usage as e:
        print(f"cedar-odcs: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
