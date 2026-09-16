//! Symbolic proofs, in two modes.
//!
//! `prove DIR` proves one use case, the folder being its own
//! statement of what must hold:
//!
//!   - never-errors: each policy in `DIR/policies.cedar` evaluates
//!     without error under the schema `DIR`'s build wrote, for every
//!     request in every request environment.
//!   - guardrail no-ops: every `*.cedar` under `DIR/guardrails/` is a
//!     forbid stating an invariant ("support never updates",
//!     "restricted is unreadable", "undeclared fields fail closed");
//!     adding it changes no decision, which proves the invariant
//!     already held. Whatever is in the directory applies; there is no
//!     manifest.
//!
//! `prove-history ROOT` proves the chain of iterations that built the
//! orders use case, and the reservations use case's own short chain.
//! For every iteration it runs the two proofs above against that
//! iteration's policies, plus, for the first two, spec equivalence:
//! the policy set is decision-for-decision equivalent to a one-or-two-
//! policy behavioral spec. It also runs the reveal: with `owner`
//! declared optional in the schema (modeling a store that may not know
//! an order), Cedar's validator rejects the unguarded `resource.owner`
//! access in the object-level policies, the same gap the corpus pins
//! as runtime evaluation errors. The field policies' `has` guards
//! pass.
//!
//! Then, across iterations (iteration 8, provable composition):
//!
//!   - preservation: for each consecutive pair, under the newer
//!     schema, the older and newer policy sets decide every action of
//!     the older iteration identically. This is the theorem behind
//!     the carried corpora. A pair may declare revisions (policies
//!     added to the older set, naming the one widening the newer
//!     iteration made) and restrictions (forbids added to both sides,
//!     confining the comparison to a region such as direct mode).
//!     Without a declared revision the pair must differ, and the
//!     runner shows that it does.
//!   - the final set: every guardrail the live use case carries is
//!     proven a no-op against it again, and every retired guardrail is
//!     shown to fail, so the retirement list is checked rather than
//!     asserted.
//!
//! Everything the chain reads that is not a use case's live policies
//! lives in `history/chain/`: the hand-written schemas, the specs, the
//! declared revisions and restrictions, and the retired guardrails.
//!
//! Requires the cvc5 solver; see README.md in this directory.

use anyhow::{anyhow, bail, Context, Result};
use cedar_policy::{PolicySet, RequestEnv, Schema};
use cedar_policy_symcc::{
    solver::LocalSolver, CedarSymCompiler, CompiledPolicy, CompiledPolicySet,
};
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::str::FromStr;

fn read(path: &Path) -> String {
    std::fs::read_to_string(path).unwrap_or_else(|e| panic!("reading {}: {e}", path.display()))
}

fn load_schema(text: &str) -> Result<Schema> {
    let (schema, _warnings) = Schema::from_cedarschema_str(text)?;
    Ok(schema)
}

fn stem(path: &Path) -> String {
    path.file_stem().unwrap().to_string_lossy().into_owned()
}

/// A path as it reads in the runner's output: relative to the
/// repository root when it is under it, absolute otherwise.
fn shown(root: &Path, path: &Path) -> String {
    path.strip_prefix(root).unwrap_or(path).to_string_lossy().into_owned()
}

struct Tally {
    pass: usize,
    fail: usize,
    shown: usize, // differences the runner expected and displayed
}

type Compiler = CedarSymCompiler<LocalSolver>;

/// The action of a request environment, as it reads in a policy:
/// `Action::"ReadOrder"`.
fn action_of(env: &RequestEnv) -> String {
    env.action().to_string()
}

/// Whether policy sets `a` and `b` produce the same decision for every
/// request in every given environment. On a difference, returns the
/// action it was found under and the counterexample.
async fn same_decisions(
    compiler: &mut Compiler,
    schema: &Schema,
    a: &PolicySet,
    b: &PolicySet,
    envs: &[RequestEnv],
) -> Result<Option<(String, String)>> {
    for env in envs {
        let ca = CompiledPolicySet::compile(a, env, schema)
            .with_context(|| format!("compiling base set under {}", action_of(env)))?;
        let cb = CompiledPolicySet::compile(b, env, schema)
            .with_context(|| format!("compiling candidate set under {}", action_of(env)))?;
        if let Some(cex) = compiler
            .check_equivalent_with_counterexample_opt(&ca, &cb)
            .await?
        {
            return Ok(Some((action_of(env), cex.to_string())));
        }
    }
    Ok(None)
}

/// Prove that policy sets `a` and `b` produce the same decision for
/// every request in every request environment of `schema`.
async fn prove_equivalent(
    compiler: &mut Compiler,
    schema: &Schema,
    a: &PolicySet,
    b: &PolicySet,
    label: &str,
    tally: &mut Tally,
) -> Result<()> {
    let envs: Vec<RequestEnv> = schema.request_envs().collect();
    prove_equivalent_in(compiler, schema, a, b, &envs, label, tally).await
}

async fn prove_equivalent_in(
    compiler: &mut Compiler,
    schema: &Schema,
    a: &PolicySet,
    b: &PolicySet,
    envs: &[RequestEnv],
    label: &str,
    tally: &mut Tally,
) -> Result<()> {
    match same_decisions(compiler, schema, a, b, envs).await? {
        None => {
            println!("  PASS  {label}");
            tally.pass += 1;
        }
        Some((action, cex)) => {
            println!("  FAIL  {label}");
            println!("        differs under {action}; counterexample: {cex}");
            tally.fail += 1;
        }
    }
    Ok(())
}

/// Show that policy sets `a` and `b` differ, as the runner expects
/// them to: a declared revision made visible, or a retired guardrail
/// shown to forbid something the final set allows.
async fn show_difference(
    compiler: &mut Compiler,
    schema: &Schema,
    a: &PolicySet,
    b: &PolicySet,
    envs: &[RequestEnv],
    label: &str,
    tally: &mut Tally,
) -> Result<()> {
    match same_decisions(compiler, schema, a, b, envs).await? {
        Some((action, _cex)) => {
            println!("  SHOWN {label}: differs under {action}, as expected");
            tally.shown += 1;
        }
        None => {
            println!("  FAIL  {label}: expected a difference and found none");
            tally.fail += 1;
        }
    }
    Ok(())
}

/// Prove every policy in the set evaluates without error, for every
/// request in every request environment.
async fn prove_never_errors(
    compiler: &mut Compiler,
    schema: &Schema,
    pset: &PolicySet,
    tally: &mut Tally,
) -> Result<()> {
    let envs: Vec<RequestEnv> = schema.request_envs().collect();
    for policy in pset.policies() {
        let policy_id = policy.id().to_string();
        let annotation = policy
            .annotation("id")
            .map(|a| a.to_string())
            .unwrap_or_else(|| policy_id.clone());
        let mut ok = true;
        for env in &envs {
            let compiled = CompiledPolicy::compile(policy, env, schema)?;
            if !compiler.check_never_errors_opt(&compiled).await? {
                ok = false;
                break;
            }
        }
        if ok {
            println!("  PASS  {annotation} never errors");
            tally.pass += 1;
        } else {
            println!("  FAIL  {annotation} can error");
            tally.fail += 1;
        }
    }
    Ok(())
}

/// Prove every guardrail file of a directory a no-op against a policy
/// set: the invariant each one states already holds.
async fn prove_guardrails(
    compiler: &mut Compiler,
    schema: &Schema,
    policy_text: &str,
    pset: &PolicySet,
    files: &[PathBuf],
    tally: &mut Tally,
) -> Result<()> {
    for file in files {
        let combined = joined(policy_text, &[read(file)])?;
        let label = format!("guardrail is a no-op: {}", stem(file));
        prove_equivalent(compiler, schema, pset, &combined, &label, tally).await?;
    }
    Ok(())
}

/// The reveal: retype each policy under a schema where `owner` is
/// optional, modeling an entity store that may not know an order.
/// Policies with bare `resource.owner` access fail validation; the
/// guarded field policies pass.
fn optional_owner_reveal(schema_text: &str, pset: &PolicySet) -> Result<()> {
    let optional = schema_text.replace("owner: User", "owner?: User");
    let schema = load_schema(&optional)?;
    let envs: Vec<RequestEnv> = schema.request_envs().collect();
    println!("  with `owner?: User` (the store may not know an order):");
    for policy in pset.policies() {
        let annotation = policy
            .annotation("id")
            .map(|a| a.to_string())
            .unwrap_or_else(|| policy.id().to_string());
        let validates = envs
            .iter()
            .all(|env| CompiledPolicy::compile(policy, env, &schema).is_ok());
        if validates {
            println!("    validates   {annotation}");
        } else {
            println!("    REJECTED    {annotation} (unguarded attribute access)");
        }
    }
    Ok(())
}

// ------------------------------------------------------------ paths

/// The Cedar schema a build wrote for a use case directory: the one
/// `*.cedarschema` under `contract/generated/`, the use case shape, or
/// under `generated/`, the shape before it, that is not an entities
/// schema.
fn built_schema(dir: &Path) -> Result<PathBuf> {
    for generated in [dir.join("contract/generated"), dir.join("generated")] {
        if !generated.is_dir() {
            continue;
        }
        let mut found: Vec<PathBuf> = std::fs::read_dir(&generated)?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().and_then(|e| e.to_str()) == Some("cedarschema"))
            .filter(|p| !p.file_name().unwrap().to_string_lossy().contains("entities"))
            .collect();
        found.sort();
        match found.len() {
            0 => continue,
            1 => return Ok(found.remove(0)),
            _ => bail!("{} holds more than one built schema", generated.display()),
        }
    }
    bail!("no built schema under {}: run the use case's build first", dir.display())
}

/// Every `*.cedar` under `dir/guardrails/`, in a stable order. A
/// directory that is not there is no guardrails, not a failure.
fn guardrail_files(dir: &Path) -> Vec<PathBuf> {
    let mut files: Vec<PathBuf> = match std::fs::read_dir(dir.join("guardrails")) {
        Ok(entries) => entries
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().and_then(|e| e.to_str()) == Some("cedar"))
            .collect(),
        Err(_) => Vec::new(),
    };
    files.sort();
    files
}

fn joined(base: &str, extras: &[String]) -> Result<PolicySet> {
    let mut text = base.to_string();
    for extra in extras {
        text.push('\n');
        text.push_str(extra);
    }
    Ok(PolicySet::from_str(&text)?)
}

// ------------------------------------------- prove DIR: one use case

async fn prove_use_case(compiler: &mut Compiler, dir: &Path, tally: &mut Tally) -> Result<()> {
    println!("=== {} ===", dir.display());
    let schema = load_schema(&read(&built_schema(dir)?))?;
    let policy_text = read(&dir.join("policies.cedar"));
    let pset = PolicySet::from_str(&policy_text)?;

    prove_never_errors(compiler, &schema, &pset, tally).await?;
    let files = guardrail_files(dir);
    prove_guardrails(compiler, &schema, &policy_text, &pset, &files, tally).await?;
    Ok(())
}

// ------------------------------------- prove-history: the tables

/// Where each snapshot of the chain sits, relative to the repository
/// root. The snapshots live under `history/`; this table is the one
/// place those paths are written.
const SNAPSHOTS: &[(&str, &str)] = &[
    ("bola-reads", "history/bola-reads"),
    ("bola-writes", "history/bola-writes"),
    ("field-reads", "history/field-reads"),
    ("field-writes", "history/field-writes"),
    ("function-level", "history/function-level"),
    ("on-behalf-of", "history/on-behalf-of"),
    ("contract", "history/contract"),
    ("row-filtering", "history/row-filtering"),
];

/// Everything the chain reads that is not a use case's live policies.
fn chain(root: &Path) -> PathBuf {
    root.join("history/chain")
}

struct Iteration {
    name: &'static str,
    /// Whether the policies are a live use case's (`usecases/<name>/`)
    /// rather than a snapshot's.
    live: bool,
    /// A behavioral spec under `history/chain/specs/`.
    spec: Option<&'static str>,
    /// For a snapshot, the guardrails that iteration was proven
    /// against, each `<snapshot>/<file>` under that snapshot's own
    /// `guardrails/` or `retired/<file>` under
    /// `history/chain/retired/`. A live use case names none: whatever
    /// is in its `guardrails/` applies.
    guardrails: &'static [&'static str],
}

const ITERATIONS: &[Iteration] = &[
    Iteration {
        name: "bola-reads",
        live: false,
        spec: Some("bola-reads.spec.cedar"),
        guardrails: &[],
    },
    Iteration {
        name: "bola-writes",
        live: false,
        spec: Some("bola-writes.spec.cedar"),
        guardrails: &["retired/support-never-updates.cedar"],
    },
    Iteration {
        name: "field-reads",
        live: false,
        spec: None,
        guardrails: &[
            "field-reads/fail-closed.cedar",
            "field-reads/restricted-unreadable.cedar",
            "field-reads/support-confidential.cedar",
        ],
    },
    // Iteration 4 carries the applicable prior guardrails the way the
    // corpora are carried: proven again against the grown policy set.
    Iteration {
        name: "field-writes",
        live: false,
        spec: None,
        guardrails: &[
            "retired/support-never-updates.cedar",
            "field-reads/fail-closed.cedar",
            "field-reads/restricted-unreadable.cedar",
            "field-reads/support-confidential.cedar",
            "field-writes/mass-assignment-fail-closed.cedar",
            "field-writes/system-fields-unwritable.cedar",
            "retired/writes-require-ownership.cedar",
        ],
    },
    // Iteration 5 grants the support role an object-level update, so
    // two earlier guardrails are retired knowingly: support-never-
    // updates and writes-require-ownership no longer hold, and
    // role-writes-only-role-fields bounds the path that replaced them.
    Iteration {
        name: "function-level",
        live: false,
        spec: None,
        guardrails: &[
            "field-reads/fail-closed.cedar",
            "field-reads/restricted-unreadable.cedar",
            "field-reads/support-confidential.cedar",
            "field-writes/mass-assignment-fail-closed.cedar",
            "field-writes/system-fields-unwritable.cedar",
            "function-level/refund-requires-finance.cedar",
            "function-level/cancel-requires-owner-or-support.cedar",
            "function-level/role-writes-only-role-fields.cedar",
            "function-level/refund-implies-no-read.cedar",
        ],
    },
    // Iteration 6 gives every policy a mode. Guardrails that mention
    // ownership or a role are revised to the acted-for party and to
    // direct mode; the mode-free ones are carried as they are.
    Iteration {
        name: "on-behalf-of",
        live: false,
        spec: None,
        guardrails: &[
            "field-reads/fail-closed.cedar",
            "field-reads/restricted-unreadable.cedar",
            "field-writes/mass-assignment-fail-closed.cedar",
            "field-writes/system-fields-unwritable.cedar",
            "function-level/refund-requires-finance.cedar",
            "on-behalf-of/support-confidential.cedar",
            "on-behalf-of/cancel-requires-owner-or-support.cedar",
            "on-behalf-of/role-writes-only-role-fields.cedar",
            "on-behalf-of/refund-implies-no-read.cedar",
            "on-behalf-of/acting-bounded-by-ownership.cedar",
            "on-behalf-of/acting-reads-customer-levels-only.cedar",
            "on-behalf-of/acting-writes-owner-fields-only.cedar",
        ],
    },
    // Iteration 7 changes no policy. Its schema is the one the build
    // wrote from the data contract (see SCHEMA_OVERRIDES), so this
    // entry proves the generated schema types the policies and admits
    // the same guardrails as the hand-written one.
    Iteration {
        name: "contract",
        live: false,
        spec: None,
        guardrails: &[
            "field-reads/fail-closed.cedar",
            "field-reads/restricted-unreadable.cedar",
            "field-writes/mass-assignment-fail-closed.cedar",
            "field-writes/system-fields-unwritable.cedar",
            "function-level/refund-requires-finance.cedar",
            "on-behalf-of/support-confidential.cedar",
            "on-behalf-of/cancel-requires-owner-or-support.cedar",
            "on-behalf-of/role-writes-only-role-fields.cedar",
            "on-behalf-of/refund-implies-no-read.cedar",
            "on-behalf-of/acting-bounded-by-ownership.cedar",
            "on-behalf-of/acting-reads-customer-levels-only.cedar",
            "on-behalf-of/acting-writes-owner-fields-only.cedar",
        ],
    },
    // Iteration 9 adds the list verb, which has no order to own. The
    // guardrail that bounds acting mode by ownership names the order
    // verbs explicitly, so the list call stays outside it.
    Iteration {
        name: "row-filtering",
        live: false,
        spec: None,
        guardrails: &[
            "field-reads/fail-closed.cedar",
            "field-reads/restricted-unreadable.cedar",
            "field-writes/mass-assignment-fail-closed.cedar",
            "field-writes/system-fields-unwritable.cedar",
            "function-level/refund-requires-finance.cedar",
            "on-behalf-of/support-confidential.cedar",
            "on-behalf-of/cancel-requires-owner-or-support.cedar",
            "on-behalf-of/role-writes-only-role-fields.cedar",
            "on-behalf-of/refund-implies-no-read.cedar",
            "row-filtering/acting-bounded-by-ownership.cedar",
            "on-behalf-of/acting-reads-customer-levels-only.cedar",
            "on-behalf-of/acting-writes-owner-fields-only.cedar",
        ],
    },
    // The orders use case, iteration 11: iteration 9's policies, the
    // schema its own build wrote, the guardrails in its folder.
    Iteration { name: "orders", live: true, spec: None, guardrails: &[] },
    // The reservations use case, iterations 11 to 13: access by
    // possession of a record locator and the holder's last name.
    Iteration { name: "reservations", live: true, spec: None, guardrails: &[] },
];

fn iteration(name: &str) -> &'static Iteration {
    ITERATIONS
        .iter()
        .find(|i| i.name == name)
        .unwrap_or_else(|| panic!("no iteration named {name}"))
}

/// The directory holding an iteration's policies: the use case's own
/// folder, or the snapshot's place in SNAPSHOTS.
fn dir_of(root: &Path, name: &str) -> PathBuf {
    if iteration(name).live {
        return root.join("usecases").join(name);
    }
    let (_, dir) = SNAPSHOTS
        .iter()
        .find(|(snapshot, _)| *snapshot == name)
        .unwrap_or_else(|| panic!("no snapshot directory for {name}"));
    root.join(dir)
}

/// The guardrail files an iteration is proven against: the files its
/// table entry names, or, for a live use case, everything in its
/// `guardrails/`.
fn guardrails_of(root: &Path, it: &Iteration) -> Vec<PathBuf> {
    if it.live {
        return guardrail_files(&dir_of(root, it.name));
    }
    it.guardrails
        .iter()
        .map(|entry| match entry.split_once('/') {
            Some(("retired", file)) => chain(root).join("retired").join(file),
            Some((snapshot, file)) => dir_of(root, snapshot).join("guardrails").join(file),
            None => panic!("guardrail {entry} names no directory"),
        })
        .collect()
}

/// A consecutive pair of iterations whose composition is proven.
struct Pair {
    older: &'static str,
    newer: &'static str,
    /// Policies added to the older set before comparing: the widenings
    /// the newer iteration declared. Without them the pair must differ.
    /// Files under `history/chain/revisions/`.
    revisions: &'static [&'static str],
    /// Forbids added to both sets before comparing, confining the
    /// comparison to a region of the request space. Files under
    /// `history/chain/restrictions/`.
    restrictions: &'static [&'static str],
}

const PAIRS: &[Pair] = &[
    Pair { older: "bola-reads", newer: "bola-writes", revisions: &[], restrictions: &[] },
    Pair { older: "bola-writes", newer: "field-reads", revisions: &[], restrictions: &[] },
    Pair { older: "field-reads", newer: "field-writes", revisions: &[], restrictions: &[] },
    // Iteration 5 revised carried decisions in two places: support may
    // update any order, and support may set fields whose writer is
    // "support". The design document declared the first; the prover
    // found the second. Those two widenings, and nothing else,
    // separate the two sets.
    Pair {
        older: "field-writes",
        newer: "function-level",
        revisions: &[
            "function-level/support-updates-any-order.cedar",
            "function-level/support-updates-support-fields.cedar",
        ],
        restrictions: &[],
    },
    // Iteration 6 revised every policy for mode and promised no change
    // in direct mode. The comparison is confined to that region.
    Pair {
        older: "function-level",
        newer: "on-behalf-of",
        revisions: &[],
        restrictions: &["direct-mode.cedar"],
    },
    // Iteration 7 generates the schema and the tag maps and leaves the
    // policies alone; the pair proves the generated schema decides as
    // the hand-written one did.
    Pair { older: "on-behalf-of", newer: "contract", revisions: &[], restrictions: &[] },
    // Iteration 9 appends one permit for the list verb. Both iterations
    // share the generated schema, which now declares that verb, so the
    // new permit is a declared revision on it; the six order actions
    // are proven untouched.
    Pair {
        older: "contract",
        newer: "row-filtering",
        revisions: &["row-filtering/anyone-lists-orders.cedar"],
        restrictions: &[],
    },
    // The move to the use case shape changes no policy: the use case
    // decides as iteration 9 did, under the schema its build wrote.
    Pair { older: "row-filtering", newer: "orders", revisions: &[], restrictions: &[] },
];

/// The live use case that closes each chain. Its `guardrails/` is the
/// chain's current invariant set, proven against its policies, and
/// every retired guardrail of the chain must differ from them.
const FINALS: &[&str] = &["orders", "reservations"];

/// Guardrails that no longer hold, each with the final set it must
/// differ from and the iteration that retired it. The files are under
/// `history/chain/retired/`, and the runner shows that each one really
/// does fail.
const RETIRED: &[(&str, &str, &str)] = &[
    (
        "lookup-requires-pair.cedar",
        "reservations",
        "iteration 13 lets a specialist look up without a pair; revised to lookup-requires-pair-or-specialist",
    ),
    (
        "read-requires-pair.cedar",
        "reservations",
        "iteration 13 lets a specialist read without a pair; revised to read-requires-pair-or-specialist",
    ),
    (
        "writes-require-pair.cedar",
        "reservations",
        "iteration 13 lets a specialist write remarks and cancel without a pair; revised to writes-require-pair-or-specialist",
    ),
    (
        "support-never-updates.cedar",
        "orders",
        "iteration 5 granted the support role an object-level update",
    ),
    (
        "writes-require-ownership.cedar",
        "orders",
        "iteration 5 opened a role-granted write path, bounded by role-writes-only-role-fields",
    ),
];

/// Iterations whose schema is a build output rather than a file in
/// `history/chain/schemas/`: the iteration whose directory holds it.
const SCHEMA_OVERRIDES: &[(&str, &str)] = &[
    ("contract", "contract"),
    ("row-filtering", "contract"),
    ("orders", "orders"),
    ("reservations", "reservations"),
];

fn schema_path(root: &Path, name: &str) -> Result<PathBuf> {
    match SCHEMA_OVERRIDES.iter().find(|(i, _)| *i == name) {
        Some((_, owner)) => built_schema(&dir_of(root, owner)),
        None => Ok(chain(root).join(format!("schemas/{name}.cedarschema"))),
    }
}

fn policies_of(root: &Path, name: &str) -> String {
    read(&dir_of(root, name).join("policies.cedar"))
}

// ------------------------------------- prove-history: the two passes

async fn prove_iterations(compiler: &mut Compiler, root: &Path, tally: &mut Tally) -> Result<()> {
    for it in ITERATIONS {
        println!("\n=== {} ===", it.name);
        let schema_text = read(&schema_path(root, it.name)?);
        let schema = load_schema(&schema_text)?;
        let policy_text = policies_of(root, it.name);
        let pset = PolicySet::from_str(&policy_text)?;

        prove_never_errors(compiler, &schema, &pset, tally).await?;

        if let Some(spec) = it.spec {
            let spec = PolicySet::from_str(&read(&chain(root).join("specs").join(spec)))?;
            prove_equivalent(
                compiler,
                &schema,
                &pset,
                &spec,
                "equivalent to the behavioral spec",
                tally,
            )
            .await?;
        }

        let files = guardrails_of(root, it);
        prove_guardrails(compiler, &schema, &policy_text, &pset, &files, tally).await?;

        optional_owner_reveal(&schema_text, &pset)?;
    }
    Ok(())
}

async fn prove_composition(compiler: &mut Compiler, root: &Path, tally: &mut Tally) -> Result<()> {
    println!("\n=== composition: preservation between iterations ===");
    for pair in PAIRS {
        let older_schema = load_schema(&read(&schema_path(root, pair.older)?))?;
        let older_actions: BTreeSet<String> =
            older_schema.actions().map(|a| a.to_string()).collect();
        let newer_schema = load_schema(&read(&schema_path(root, pair.newer)?))?;
        let envs: Vec<RequestEnv> = newer_schema
            .request_envs()
            .filter(|env| older_actions.contains(&action_of(env)))
            .collect();

        let restrictions: Vec<String> = pair
            .restrictions
            .iter()
            .map(|p| read(&chain(root).join("restrictions").join(p)))
            .collect();
        let revisions: Vec<String> = pair
            .revisions
            .iter()
            .map(|p| read(&chain(root).join("revisions").join(p)))
            .collect();

        let older_text = policies_of(root, pair.older);
        let newer_text = policies_of(root, pair.newer);
        let newer = joined(&newer_text, &restrictions)?;
        let older_plain = joined(&older_text, &restrictions)?;
        let mut with_revisions = revisions.clone();
        with_revisions.extend(restrictions.iter().cloned());
        let older_revised = joined(&older_text, &with_revisions)?;

        let mut label = format!("{} preserved in {}", pair.older, pair.newer);
        if !pair.revisions.is_empty() {
            let names: Vec<String> =
                pair.revisions.iter().map(|p| stem(Path::new(p))).collect();
            label.push_str(&format!(" given the declared revision {}", names.join(", ")));
        }
        if !pair.restrictions.is_empty() {
            let names: Vec<String> =
                pair.restrictions.iter().map(|p| stem(Path::new(p))).collect();
            label.push_str(&format!(" within {}", names.join(", ")));
        }
        prove_equivalent_in(compiler, &newer_schema, &older_revised, &newer, &envs, &label, tally)
            .await?;
        let actions: Vec<String> = envs.iter().map(action_of).collect::<BTreeSet<_>>().into_iter().collect();
        println!("        actions compared: {}", actions.join(", "));

        if !pair.revisions.is_empty() {
            let label = format!(
                "without the declared revision, {} and {} differ",
                pair.older, pair.newer
            );
            show_difference(compiler, &newer_schema, &older_plain, &newer, &envs, &label, tally)
                .await?;
        }
    }

    for final_name in FINALS {
        println!("\n=== composition: every {final_name} guardrail against the final set ===");
        let schema = load_schema(&read(&schema_path(root, final_name)?))?;
        let envs: Vec<RequestEnv> = schema.request_envs().collect();
        let final_text = policies_of(root, final_name);
        let final_set = PolicySet::from_str(&final_text)?;

        for path in guardrail_files(&dir_of(root, final_name)) {
            let combined = joined(&final_text, &[read(&path)])?;
            let label = format!("carried  {}", shown(root, &path));
            prove_equivalent_in(compiler, &schema, &final_set, &combined, &envs, &label, tally)
                .await?;
        }
        for (file, _, reason) in RETIRED.iter().filter(|(_, against, _)| against == final_name) {
            let path = chain(root).join("retired").join(file);
            let combined = joined(&final_text, &[read(&path)])?;
            let label = format!("retired  {}: {reason}", shown(root, &path));
            show_difference(compiler, &schema, &final_set, &combined, &envs, &label, tally).await?;
        }
    }
    Ok(())
}

// ------------------------------------------------------- the command

const USAGE: &str = "usage: cargo run -- prove <use case dir>\n       \
                     cargo run -- prove-history <repository root>";

enum Mode {
    /// One use case's own folder.
    UseCase(PathBuf),
    /// The chain, from the repository root.
    History(PathBuf),
}

/// The repository root when no argument names one: the analysis
/// crate's directory's parent.
fn default_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
}

/// Whether a directory is the repository root, so that the bare
/// argument `check.sh` passes still means the chain.
fn is_repo_root(dir: &Path) -> bool {
    dir.join("analysis/Cargo.toml").is_file()
}

fn mode() -> Result<Mode> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.split_first() {
        None => Ok(Mode::History(default_root())),
        Some((first, rest)) if first == "prove" => match rest.first() {
            Some(dir) => Ok(Mode::UseCase(PathBuf::from(dir))),
            None => Err(anyhow!("prove needs a use case directory\n{USAGE}")),
        },
        Some((first, rest)) if first == "prove-history" => Ok(Mode::History(
            rest.first().map(PathBuf::from).unwrap_or_else(default_root),
        )),
        Some((first, rest)) if rest.is_empty() && is_repo_root(Path::new(first)) => {
            Ok(Mode::History(PathBuf::from(first)))
        }
        Some((first, _)) => Err(anyhow!("{first} is neither a mode nor the repository root\n{USAGE}")),
    }
}

/// Spawn cvc5 from $CVC5, PATH, or the copy bundled in .tools.
fn solver() -> Result<LocalSolver> {
    let path = std::env::var("CVC5").unwrap_or_else(|_| {
        let bundled = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join(".tools/cvc5-macOS-arm64-static/bin/cvc5");
        if bundled.exists() {
            bundled.to_string_lossy().into_owned()
        } else {
            "cvc5".into()
        }
    });
    Ok(LocalSolver::from_command(
        tokio::process::Command::new(path).args(["--lang", "smt", "--tlimit=60000"]),
    )?)
}

#[tokio::main]
async fn main() -> Result<()> {
    let mode = mode()?;
    let mut compiler = CedarSymCompiler::new(solver()?)?;
    let mut tally = Tally { pass: 0, fail: 0, shown: 0 };

    match mode {
        Mode::UseCase(dir) => {
            prove_use_case(&mut compiler, &dir, &mut tally).await?;
        }
        Mode::History(root) => {
            println!("root: {}", root.display());
            prove_iterations(&mut compiler, &root, &mut tally).await?;
            prove_composition(&mut compiler, &root, &mut tally).await?;
        }
    }

    println!(
        "\n{} proved, {} failed, {} differences shown as expected",
        tally.pass, tally.fail, tally.shown
    );
    if tally.fail > 0 {
        std::process::exit(1);
    }
    Ok(())
}
