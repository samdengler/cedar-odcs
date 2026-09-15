//! Symbolic proofs over each iteration's policy set, and over the
//! composition of the iterations.
//!
//! For every iteration this runner proves, over ALL possible requests
//! (not the corpus's samples):
//!
//!   - spec equivalence: the policy set is decision-for-decision
//!     equivalent to a one-or-two-policy behavioral spec, or
//!   - guardrail no-ops: adding a forbid that states an invariant
//!     ("support never updates", "restricted is unreadable",
//!     "undeclared fields fail closed") changes no decision, which
//!     proves the invariant already held, and
//!   - never-errors: each policy evaluates without error under the
//!     schema's assumptions.
//!
//! It also runs the reveal: with `owner` declared optional in the
//! schema (modeling a store that may not know an order), Cedar's
//! validator rejects the unguarded `resource.owner` access in the
//! object-level policies, the same gap the corpus pins as runtime
//! evaluation errors. The field policies' `has` guards pass.
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
//!   - every guardrail against the final set: carried ones proven
//!     again, revised ones pointed at their successors, retired ones
//!     shown to fail, so the retirement list is checked rather than
//!     asserted.
//!
//! Requires the cvc5 solver; see README.md in this directory.

use anyhow::{Context, Result};
use cedar_policy::{PolicySet, RequestEnv, Schema};
use cedar_policy_symcc::{
    solver::LocalSolver, CedarSymCompiler, CompiledPolicy, CompiledPolicySet,
};
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::str::FromStr;

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf()
}

fn read(path: &Path) -> String {
    std::fs::read_to_string(path).unwrap_or_else(|e| panic!("reading {}: {e}", path.display()))
}

fn load_schema(text: &str) -> Result<Schema> {
    let (schema, _warnings) = Schema::from_cedarschema_str(text)?;
    Ok(schema)
}

fn stem(path: &str) -> String {
    Path::new(path).file_stem().unwrap().to_string_lossy().into_owned()
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

struct Iteration {
    name: &'static str,
    /// Directory under the repository root holding policies.cedar; the
    /// name itself for the numbered iterations, usecases/<name> for
    /// the use cases running on core.
    dir: &'static str,
    /// The chain of policy sets this iteration belongs to. Preservation
    /// pairs and the final-set guardrail pass run per chain.
    chain: &'static str,
    spec: Option<&'static str>,
    guardrails: &'static [&'static str],
}

const ITERATIONS: &[Iteration] = &[
    Iteration {
        name: "bola-reads",
        dir: "bola-reads",
        chain: "orders",
        spec: Some("specs/bola-reads.spec.cedar"),
        guardrails: &[],
    },
    Iteration {
        name: "bola-writes",
        dir: "bola-writes",
        chain: "orders",
        spec: Some("specs/bola-writes.spec.cedar"),
        guardrails: &["guardrails/bola-writes/support-never-updates.cedar"],
    },
    Iteration {
        name: "field-reads",
        dir: "field-reads",
        chain: "orders",
        spec: None,
        guardrails: &[
            "guardrails/field-reads/fail-closed.cedar",
            "guardrails/field-reads/restricted-unreadable.cedar",
            "guardrails/field-reads/support-confidential.cedar",
        ],
    },
    // Iteration 4 carries the applicable prior guardrails the way the
    // corpora are carried: proven again against the grown policy set.
    Iteration {
        name: "field-writes",
        dir: "field-writes",
        chain: "orders",
        spec: None,
        guardrails: &[
            "guardrails/bola-writes/support-never-updates.cedar",
            "guardrails/field-reads/fail-closed.cedar",
            "guardrails/field-reads/restricted-unreadable.cedar",
            "guardrails/field-reads/support-confidential.cedar",
            "guardrails/field-writes/mass-assignment-fail-closed.cedar",
            "guardrails/field-writes/system-fields-unwritable.cedar",
            "guardrails/field-writes/writes-require-ownership.cedar",
        ],
    },
    // Iteration 5 grants the support role an object-level update, so
    // two earlier guardrails are retired knowingly: support-never-
    // updates and writes-require-ownership no longer hold, and
    // role-writes-only-role-fields bounds the path that replaced them.
    Iteration {
        name: "function-level",
        dir: "function-level",
        chain: "orders",
        spec: None,
        guardrails: &[
            "guardrails/field-reads/fail-closed.cedar",
            "guardrails/field-reads/restricted-unreadable.cedar",
            "guardrails/field-reads/support-confidential.cedar",
            "guardrails/field-writes/mass-assignment-fail-closed.cedar",
            "guardrails/field-writes/system-fields-unwritable.cedar",
            "guardrails/function-level/refund-requires-finance.cedar",
            "guardrails/function-level/cancel-requires-owner-or-support.cedar",
            "guardrails/function-level/role-writes-only-role-fields.cedar",
            "guardrails/function-level/refund-implies-no-read.cedar",
        ],
    },
    // Iteration 6 gives every policy a mode. Guardrails that mention
    // ownership or a role are revised to the acted-for party and to
    // direct mode; the mode-free ones are carried as they are.
    Iteration {
        name: "on-behalf-of",
        dir: "on-behalf-of",
        chain: "orders",
        spec: None,
        guardrails: &[
            "guardrails/field-reads/fail-closed.cedar",
            "guardrails/field-reads/restricted-unreadable.cedar",
            "guardrails/field-writes/mass-assignment-fail-closed.cedar",
            "guardrails/field-writes/system-fields-unwritable.cedar",
            "guardrails/function-level/refund-requires-finance.cedar",
            "guardrails/on-behalf-of/support-confidential.cedar",
            "guardrails/on-behalf-of/cancel-requires-owner-or-support.cedar",
            "guardrails/on-behalf-of/role-writes-only-role-fields.cedar",
            "guardrails/on-behalf-of/refund-implies-no-read.cedar",
            "guardrails/on-behalf-of/acting-bounded-by-ownership.cedar",
            "guardrails/on-behalf-of/acting-reads-customer-levels-only.cedar",
            "guardrails/on-behalf-of/acting-writes-owner-fields-only.cedar",
        ],
    },
    // Iteration 7 changes no policy. Its schema is the one the build
    // wrote from the data contract (see SCHEMA_OVERRIDES), so this
    // entry proves the generated schema types the policies and admits
    // the same guardrails as the hand-written one.
    Iteration {
        name: "contract",
        dir: "contract",
        chain: "orders",
        spec: None,
        guardrails: &[
            "guardrails/field-reads/fail-closed.cedar",
            "guardrails/field-reads/restricted-unreadable.cedar",
            "guardrails/field-writes/mass-assignment-fail-closed.cedar",
            "guardrails/field-writes/system-fields-unwritable.cedar",
            "guardrails/function-level/refund-requires-finance.cedar",
            "guardrails/on-behalf-of/support-confidential.cedar",
            "guardrails/on-behalf-of/cancel-requires-owner-or-support.cedar",
            "guardrails/on-behalf-of/role-writes-only-role-fields.cedar",
            "guardrails/on-behalf-of/refund-implies-no-read.cedar",
            "guardrails/on-behalf-of/acting-bounded-by-ownership.cedar",
            "guardrails/on-behalf-of/acting-reads-customer-levels-only.cedar",
            "guardrails/on-behalf-of/acting-writes-owner-fields-only.cedar",
        ],
    },
    // Iteration 9 adds the list verb, which has no order to own. The
    // guardrail that bounds acting mode by ownership names the order
    // verbs explicitly, so the list call stays outside it.
    Iteration {
        name: "row-filtering",
        dir: "row-filtering",
        chain: "orders",
        spec: None,
        guardrails: &[
            "guardrails/field-reads/fail-closed.cedar",
            "guardrails/field-reads/restricted-unreadable.cedar",
            "guardrails/field-writes/mass-assignment-fail-closed.cedar",
            "guardrails/field-writes/system-fields-unwritable.cedar",
            "guardrails/function-level/refund-requires-finance.cedar",
            "guardrails/on-behalf-of/support-confidential.cedar",
            "guardrails/on-behalf-of/cancel-requires-owner-or-support.cedar",
            "guardrails/on-behalf-of/role-writes-only-role-fields.cedar",
            "guardrails/on-behalf-of/refund-implies-no-read.cedar",
            "guardrails/row-filtering/acting-bounded-by-ownership.cedar",
            "guardrails/on-behalf-of/acting-reads-customer-levels-only.cedar",
            "guardrails/on-behalf-of/acting-writes-owner-fields-only.cedar",
        ],
    },
    // The orders use case on core: iteration 9's policies, the schema
    // core's build wrote, the same guardrails.
    Iteration {
        name: "orders",
        dir: "usecases/orders",
        chain: "orders",
        spec: None,
        guardrails: &[
            "guardrails/field-reads/fail-closed.cedar",
            "guardrails/field-reads/restricted-unreadable.cedar",
            "guardrails/field-writes/mass-assignment-fail-closed.cedar",
            "guardrails/field-writes/system-fields-unwritable.cedar",
            "guardrails/function-level/refund-requires-finance.cedar",
            "guardrails/on-behalf-of/support-confidential.cedar",
            "guardrails/on-behalf-of/cancel-requires-owner-or-support.cedar",
            "guardrails/on-behalf-of/role-writes-only-role-fields.cedar",
            "guardrails/on-behalf-of/refund-implies-no-read.cedar",
            "guardrails/row-filtering/acting-bounded-by-ownership.cedar",
            "guardrails/on-behalf-of/acting-reads-customer-levels-only.cedar",
            "guardrails/on-behalf-of/acting-writes-owner-fields-only.cedar",
        ],
    },
    // The reservations use case, iteration 11: access by possession of
    // a record locator and the holder's last name. A chain of its own.
    Iteration {
        name: "reservations",
        dir: "usecases/reservations",
        chain: "reservations",
        spec: None,
        guardrails: &[
            "guardrails/reservations/lookup-requires-pair.cedar",
            "guardrails/reservations/read-requires-pair.cedar",
            "guardrails/reservations/possession-names-the-record.cedar",
            "guardrails/reservations/fail-closed.cedar",
            "guardrails/reservations/restricted-unreadable.cedar",
            "guardrails/reservations/possession-reads-customer-levels-only.cedar",
            "guardrails/reservations/writes-require-pair.cedar",
            "guardrails/reservations/possession-writes-named-record-only.cedar",
            "guardrails/reservations/possession-writes-owner-paths-only.cedar",
            "guardrails/reservations/mass-assignment-fail-closed.cedar",
        ],
    },
];

fn iteration(name: &str) -> &'static Iteration {
    ITERATIONS
        .iter()
        .find(|i| i.name == name)
        .unwrap_or_else(|| panic!("no iteration named {name}"))
}

/// A consecutive pair of iterations whose composition is proven.
struct Pair {
    older: &'static str,
    newer: &'static str,
    /// Policies added to the older set before comparing: the widenings
    /// the newer iteration declared. Without them the pair must differ.
    revisions: &'static [&'static str],
    /// Forbids added to both sets before comparing, confining the
    /// comparison to a region of the request space.
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
            "revisions/function-level/support-updates-any-order.cedar",
            "revisions/function-level/support-updates-support-fields.cedar",
        ],
        restrictions: &[],
    },
    // Iteration 6 revised every policy for mode and promised no change
    // in direct mode. The comparison is confined to that region.
    Pair {
        older: "function-level",
        newer: "on-behalf-of",
        revisions: &[],
        restrictions: &["restrictions/direct-mode.cedar"],
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
        revisions: &["revisions/row-filtering/anyone-lists-orders.cedar"],
        restrictions: &[],
    },
    // The move to core changes no policy: the use case decides as
    // iteration 9 did, under the schema core's build wrote.
    Pair { older: "row-filtering", newer: "orders", revisions: &[], restrictions: &[] },
];

/// Guardrails that no longer hold against the final set, each with
/// the iteration that retired it and why. The runner shows that each
/// one really does fail.
const RETIRED: &[(&str, &str)] = &[
    (
        "guardrails/bola-writes/support-never-updates.cedar",
        "iteration 5 granted the support role an object-level update",
    ),
    (
        "guardrails/field-writes/writes-require-ownership.cedar",
        "iteration 5 opened a role-granted write path, bounded by role-writes-only-role-fields",
    ),
];

/// The final policy set of each chain, against which every guardrail
/// of that chain is given a status.
const FINALS: &[(&str, &str)] = &[("orders", "orders"), ("reservations", "reservations")];

/// Iterations whose schema is a build output rather than a file in
/// schemas/: the path is relative to this directory.
const SCHEMA_OVERRIDES: &[(&str, &str)] = &[
    ("contract", "../contract/generated/orders.cedarschema"),
    ("row-filtering", "../contract/generated/orders.cedarschema"),
    ("orders", "../usecases/orders/generated/order.cedarschema"),
    ("reservations", "../usecases/reservations/generated/reservation.cedarschema"),
];

fn schema_path(analysis: &Path, iteration: &str) -> PathBuf {
    match SCHEMA_OVERRIDES.iter().find(|(name, _)| *name == iteration) {
        Some((_, path)) => analysis.join(path),
        None => analysis.join(format!("schemas/{iteration}.cedarschema")),
    }
}

/// The guardrail of the same name in the latest later iteration, if
/// any: a revised guardrail is proven in its successor's form.
fn successor_of(analysis: &Path, path: &str) -> Option<String> {
    let iteration = path.split('/').nth(1)?;
    let position = ITERATIONS.iter().position(|i| i.name == iteration)?;
    let name = stem(path);
    ITERATIONS[position + 1..]
        .iter()
        .map(|later| format!("guardrails/{}/{name}.cedar", later.name))
        .filter(|candidate| analysis.join(candidate).exists())
        .last()
}

fn policies_of(root: &Path, name: &str) -> String {
    read(&root.join(iteration(name).dir).join("policies.cedar"))
}

/// The chain a guardrail file belongs to, from the iteration named by
/// its directory; None for a directory naming no iteration.
fn chain_of_guardrail(path: &str) -> Option<&'static str> {
    let name = path.split('/').nth(1)?;
    ITERATIONS.iter().find(|i| i.name == name).map(|i| i.chain)
}

fn joined(base: &str, extras: &[String]) -> Result<PolicySet> {
    let mut text = base.to_string();
    for extra in extras {
        text.push('\n');
        text.push_str(extra);
    }
    Ok(PolicySet::from_str(&text)?)
}

/// Every guardrail file under guardrails/, in a stable order.
fn all_guardrails(analysis: &Path) -> Vec<String> {
    let mut files = Vec::new();
    for dir in std::fs::read_dir(analysis.join("guardrails")).unwrap() {
        let dir = dir.unwrap().path();
        for file in std::fs::read_dir(&dir).unwrap() {
            let file = file.unwrap().path();
            if file.extension().and_then(|e| e.to_str()) != Some("cedar") {
                continue;
            }
            files.push(
                file.strip_prefix(analysis).unwrap().to_string_lossy().into_owned(),
            );
        }
    }
    files.sort();
    files
}

async fn prove_iterations(compiler: &mut Compiler, tally: &mut Tally) -> Result<()> {
    let root = repo_root();
    let analysis = root.join("analysis");

    for iteration in ITERATIONS {
        println!("\n=== {} ===", iteration.name);
        let schema_text = read(&schema_path(&analysis, iteration.name));
        let schema = load_schema(&schema_text)?;
        let policy_text = policies_of(&root, iteration.name);
        let pset = PolicySet::from_str(&policy_text)?;

        prove_never_errors(compiler, &schema, &pset, tally).await?;

        if let Some(spec_path) = iteration.spec {
            let spec = PolicySet::from_str(&read(&analysis.join(spec_path)))?;
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

        for guardrail_path in iteration.guardrails {
            let combined = joined(&policy_text, &[read(&analysis.join(guardrail_path))])?;
            let label = format!("guardrail is a no-op: {}", stem(guardrail_path));
            prove_equivalent(compiler, &schema, &pset, &combined, &label, tally).await?;
        }

        optional_owner_reveal(&schema_text, &pset)?;
    }
    Ok(())
}

async fn prove_composition(compiler: &mut Compiler, tally: &mut Tally) -> Result<()> {
    let root = repo_root();
    let analysis = root.join("analysis");

    println!("\n=== composition: preservation between iterations ===");
    for pair in PAIRS {
        let older_schema = load_schema(&read(&schema_path(&analysis, pair.older)))?;
        let older_actions: BTreeSet<String> =
            older_schema.actions().map(|a| a.to_string()).collect();
        let newer_schema = load_schema(&read(&schema_path(&analysis, pair.newer)))?;
        let envs: Vec<RequestEnv> = newer_schema
            .request_envs()
            .filter(|env| older_actions.contains(&action_of(env)))
            .collect();

        let restrictions: Vec<String> = pair
            .restrictions
            .iter()
            .map(|p| read(&analysis.join(p)))
            .collect();
        let revisions: Vec<String> = pair
            .revisions
            .iter()
            .map(|p| read(&analysis.join(p)))
            .collect();

        let older_text = policies_of(&root, pair.older);
        let newer_text = policies_of(&root, pair.newer);
        let newer = joined(&newer_text, &restrictions)?;
        let older_plain = joined(&older_text, &restrictions)?;
        let mut with_revisions = revisions.clone();
        with_revisions.extend(restrictions.iter().cloned());
        let older_revised = joined(&older_text, &with_revisions)?;

        let mut label = format!("{} preserved in {}", pair.older, pair.newer);
        if !pair.revisions.is_empty() {
            let names: Vec<String> = pair.revisions.iter().map(|p| stem(p)).collect();
            label.push_str(&format!(" given the declared revision {}", names.join(", ")));
        }
        if !pair.restrictions.is_empty() {
            let names: Vec<String> = pair.restrictions.iter().map(|p| stem(p)).collect();
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

    for (chain, final_name) in FINALS {
    println!("\n=== composition: every {chain} guardrail against the final set ({final_name}) ===");
    let schema = load_schema(&read(&schema_path(&analysis, final_name)))?;
    let envs: Vec<RequestEnv> = schema.request_envs().collect();
    let final_text = policies_of(&root, final_name);
    let final_set = PolicySet::from_str(&final_text)?;
    for path in all_guardrails(&analysis) {
        if chain_of_guardrail(&path) != Some(chain) {
            continue;
        }
        let combined = joined(&final_text, &[read(&analysis.join(&path))])?;
        if let Some((_, reason)) = RETIRED.iter().find(|(p, _)| *p == path) {
            let label = format!("retired  {path}: {reason}");
            show_difference(compiler, &schema, &final_set, &combined, &envs, &label, tally).await?;
        } else if let Some(successor) = successor_of(&analysis, &path) {
            println!("  revised {path}: superseded by {successor}");
        } else {
            let label = format!("carried  {path}");
            prove_equivalent_in(compiler, &schema, &final_set, &combined, &envs, &label, tally)
                .await?;
        }
    }
    }
    Ok(())
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
    let mut compiler = CedarSymCompiler::new(solver()?)?;
    let mut tally = Tally { pass: 0, fail: 0, shown: 0 };

    prove_iterations(&mut compiler, &mut tally).await?;
    prove_composition(&mut compiler, &mut tally).await?;

    println!(
        "\n{} proved, {} failed, {} differences shown as expected",
        tally.pass, tally.fail, tally.shown
    );
    if tally.fail > 0 {
        std::process::exit(1);
    }
    Ok(())
}
