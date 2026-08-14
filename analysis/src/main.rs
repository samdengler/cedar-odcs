//! Symbolic proofs over each iteration's policy set, in isolation.
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
//! Requires the cvc5 solver; see README.md in this directory.

// WellTypedPolicies/SymEnv are deprecated in favor of CompiledPolicySet,
// which caches compilation across queries. At this scale the simpler
// API reads better; revisit when the composition iteration grows the
// query count.
#![allow(deprecated)]

use anyhow::Result;
use cedar_policy::{PolicySet, Schema};
use cedar_policy_symcc::{
    solver::LocalSolver, CedarSymCompiler, SymEnv, WellTypedPolicies, WellTypedPolicy,
};
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

struct Tally {
    pass: usize,
    fail: usize,
}

type Compiler = CedarSymCompiler<LocalSolver>;

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
    for env in schema.request_envs() {
        use anyhow::Context;
        let ta = WellTypedPolicies::from_policies(a, &env, schema)
            .with_context(|| format!("typing base set under env {:?}", env.action()))?;
        let tb = WellTypedPolicies::from_policies(b, &env, schema)
            .with_context(|| format!("typing candidate set under env {:?}", env.action()))?;
        let sym = SymEnv::new(schema, &env)?;
        if let Some(cex) = compiler
            .check_equivalent_with_counterexample(&ta, &tb, &sym)
            .await?
        {
            println!("  FAIL  {label}");
            println!("        counterexample: {cex:?}");
            tally.fail += 1;
            return Ok(());
        }
    }
    println!("  PASS  {label}");
    tally.pass += 1;
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
    for policy in pset.policies() {
        let policy_id = policy.id().to_string();
        let annotation = policy
            .annotation("id")
            .map(|a| a.to_string())
            .unwrap_or_else(|| policy_id.clone());
        let mut ok = true;
        for env in schema.request_envs() {
            let tp = WellTypedPolicy::from_policy(policy, &env, schema)?;
            let sym = SymEnv::new(schema, &env)?;
            if !compiler.check_never_errors(&tp, &sym).await? {
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
    println!("  with `owner?: User` (the store may not know an order):");
    for policy in pset.policies() {
        let annotation = policy
            .annotation("id")
            .map(|a| a.to_string())
            .unwrap_or_else(|| policy.id().to_string());
        let mut verdicts = Vec::new();
        for env in schema.request_envs() {
            match WellTypedPolicy::from_policy(policy, &env, &schema) {
                Ok(_) => verdicts.push(true),
                Err(_) => verdicts.push(false),
            }
        }
        if verdicts.iter().all(|v| *v) {
            println!("    validates   {annotation}");
        } else {
            println!("    REJECTED    {annotation} (unguarded attribute access)");
        }
    }
    Ok(())
}

struct Iteration {
    name: &'static str,
    schema: &'static str,
    spec: Option<&'static str>,
    guardrails: &'static [&'static str],
}

const ITERATIONS: &[Iteration] = &[
    Iteration {
        name: "bola-reads",
        schema: "schemas/bola-reads.cedarschema",
        spec: Some("specs/bola-reads.spec.cedar"),
        guardrails: &[],
    },
    Iteration {
        name: "bola-writes",
        schema: "schemas/bola-writes.cedarschema",
        spec: Some("specs/bola-writes.spec.cedar"),
        guardrails: &["guardrails/bola-writes/support-never-updates.cedar"],
    },
    Iteration {
        name: "field-reads",
        schema: "schemas/field-reads.cedarschema",
        spec: None,
        guardrails: &[
            "guardrails/field-reads/fail-closed.cedar",
            "guardrails/field-reads/restricted-unreadable.cedar",
            "guardrails/field-reads/support-confidential.cedar",
        ],
    },
];

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
    let root = repo_root();
    let analysis = root.join("analysis");
    let mut compiler = CedarSymCompiler::new(solver()?)?;
    let mut tally = Tally { pass: 0, fail: 0 };

    for iteration in ITERATIONS {
        println!("\n=== {} ===", iteration.name);
        let schema_text = read(&analysis.join(iteration.schema));
        let schema = load_schema(&schema_text)?;
        let policy_text = read(&root.join(iteration.name).join("policies.cedar"));
        let pset = PolicySet::from_str(&policy_text)?;

        prove_never_errors(&mut compiler, &schema, &pset, &mut tally).await?;

        if let Some(spec_path) = iteration.spec {
            let spec = PolicySet::from_str(&read(&analysis.join(spec_path)))?;
            prove_equivalent(
                &mut compiler,
                &schema,
                &pset,
                &spec,
                "equivalent to the behavioral spec",
                &mut tally,
            )
            .await?;
        }

        for guardrail_path in iteration.guardrails {
            let combined_text = format!("{policy_text}\n{}", read(&analysis.join(guardrail_path)));
            let combined = PolicySet::from_str(&combined_text)?;
            let label = format!(
                "guardrail is a no-op: {}",
                Path::new(guardrail_path).file_stem().unwrap().to_string_lossy()
            );
            prove_equivalent(&mut compiler, &schema, &pset, &combined, &label, &mut tally).await?;
        }

        optional_owner_reveal(&schema_text, &pset)?;
    }

    println!("\n{} proved, {} failed", tally.pass, tally.fail);
    if tally.fail > 0 {
        std::process::exit(1);
    }
    Ok(())
}
