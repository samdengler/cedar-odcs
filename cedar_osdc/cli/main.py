"""cedar-osdc: the mechanism at the command line.

    cedar-osdc run-tests    usecases/reservations
    cedar-osdc authorize    usecases/reservations --principal 'User::"sam"' \\
                              --action 'Action::"ReadReservation"' --resource 'Reservation::"ABC123"'
    cedar-osdc dry-run      usecases/reservations --caller sam.json \\
                              --tool reservations___get_reservation --arg recordLocator=XYZ789 \\
                              --response record.json
    cedar-osdc check-access usecases/reservations --caller agent.json \\
                              --presented locator=ABC123 --presented lastName=SMITH
    cedar-osdc share        usecases/reservations --case "co-traveler"
    cedar-osdc build        usecases/reservations
    cedar-osdc validate     usecases/reservations
    cedar-osdc prove

Verbs match the official cedar command where the meaning is the same
(authorize, validate, run-tests, new) and add the two ideas Cedar has
no word for: a dry run of one tool call through both legs, and a
report of what an identity may do. Files are Cedar's own formats:
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
import re
import shutil
import subprocess
import sys
from pathlib import Path

import cedarpy

from cedar_osdc.engine import calls
from cedar_osdc.engine.corpus import case_files
from cedar_osdc.engine.enforce import Engine, explain
from cedar_osdc.engine.usecase import paths

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


def policy_names(policies: str) -> dict:
    """policyN -> the @id annotation, from the file's order."""
    ids = re.findall(r'@id\("([^"]+)"\)', policies)
    return {f"policy{i}": name for i, name in enumerate(ids)}


def name_of(policy_id: str, names: dict) -> str:
    return f"{policy_id} ({names[policy_id]})" if policy_id in names else policy_id


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
        policies = (root / spec["policies"]).read_text()
        entities = (root / spec["entities"]).read_text()
        names = policy_names(policies)
        print(f"\n{spec_file.relative_to(root)}")
        for case in spec["requests"]:
            total += 1
            request = {
                "principal": _ref(case["principal"]), "action": _ref(case["action"]),
                "resource": _ref(case["resource"]), "context": case.get("context", {}),
            }
            result = cedarpy.is_authorized(request, policies, entities)
            actual = "Allow" if result.decision == cedarpy.Decision.Allow else "Deny"
            reasons = sorted(result.diagnostics.reasons)
            expected_reasons = sorted(case.get("reason", []))
            expected_errors = case.get("errors", [])
            ok = (actual == case["decision"] and reasons == expected_reasons
                  and len(result.diagnostics.errors) == len(expected_errors))
            if ok:
                print(f"  PASS  {case['description']}")
            else:
                failures += 1
                print(f"  FAIL  {case['description']}")
                print(f"        expected {case['decision']} by {expected_reasons or 'no policy'}, "
                      f"got {actual} by {[name_of(r, names) for r in reasons] or 'no policy'}")
                for error in result.diagnostics.errors:
                    print(f"        error: {error}")
            exported.append({
                "name": case["description"],
                "request": {"principal": case["principal"], "action": case["action"],
                            "resource": case["resource"], "context": case.get("context", {})},
                "entities": json.loads(entities),
                "decision": case["decision"].lower(),
                "reason": case.get("reason", []),
                "num_errors": len(expected_errors),
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

def cmd_build(args):
    module = load_use_case(args.directory)
    from cedar_osdc.engine.contract import build, write
    outputs = build(module.USE_CASE.root, **module.BUILD)
    write(module.USE_CASE.root, outputs)
    for rel in outputs:
        print("wrote", rel)
    return 0


def cmd_validate(args):
    module = load_use_case(args.directory)
    use_case = module.USE_CASE
    generated = paths(use_case.root).generated
    schema_files = [f for f in sorted(generated.glob("*.cedarschema")) if f.name != "entities.cedarschema"]
    if not schema_files:
        raise Usage("no generated schema; run build first")
    cedar = shutil.which("cedar")
    if cedar is None:
        print("The cedar command is not installed. Install it with")
        print("    cargo install cedar-policy-cli")
        print("then run:")
        print(f"    cedar validate --schema {schema_files[0]} --policies {use_case.root / 'policies.cedar'}")
        return 2
    return subprocess.call([cedar, "validate", "--schema", str(schema_files[0]),
                            "--policies", str(use_case.root / "policies.cedar")])


def cmd_prove(args):
    analysis = REPO / "analysis"
    if shutil.which("cargo") is None:
        print("The proofs need Rust (cargo) and the cvc5 solver; see analysis/README.md.")
        return 2
    return subprocess.call(["cargo", "run", "--quiet", "--", str(REPO)], cwd=analysis)


def cmd_new(args):
    raise Usage("new is planned; copy usecases/reservations for now and edit usecase.py")


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cedar-osdc", description=__doc__.split("\n\n")[0])
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

    with_dir(sub.add_parser("build", help="the contract build: catalog to contract to Cedar")).set_defaults(func=cmd_build)
    with_dir(sub.add_parser("validate", help="policies against the built schema, with the cedar command")).set_defaults(func=cmd_validate)
    sub.add_parser("prove", help="the symbolic proofs, with cargo and cvc5").set_defaults(func=cmd_prove)
    with_dir(sub.add_parser("new", help="scaffold a use case (planned)")).set_defaults(func=cmd_new)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Usage as e:
        print(f"cedar-osdc: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
