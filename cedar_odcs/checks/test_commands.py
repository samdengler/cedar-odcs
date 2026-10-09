"""pytest wrapper over cedar_odcs/checks/commands.py.

Runs every command line the learning pages show (minus placeholders
and the two slow, recursive ones) from the repository root, and
requires each to exit 0 or 1 with no Traceback and no argparse
"usage:" in stderr.
"""

from pathlib import Path

from cedar_odcs.checks.commands import plan_commands, run_command

REPO_ROOT = Path(__file__).resolve().parents[2]

# Commands that are broken on the current tree today, so the test stays
# green and the debt stays visible. Empty since run 3 rewrote the pages.
KNOWN_BROKEN_COMMANDS = set()


def test_command_smoke():
    plan = plan_commands(REPO_ROOT)
    print(f"\n{len(plan.to_run)} command(s) to run, {len(plan.skipped)} skipped:")
    for line, reason in plan.skipped:
        print(f"  skip  {line}   ({reason})")

    unexpected = []
    for line in plan.to_run:
        result = run_command(line, REPO_ROOT)
        if result.ok:
            print(f"  ok            {line}")
            continue
        if line in KNOWN_BROKEN_COMMANDS:
            print(f"  known-broken  {line}  ({result.problem})")
            continue
        print(f"  FAIL          {line}  ({result.problem})")
        unexpected.append(f"{line}\n  {result.problem}\n  stderr: {result.stderr.strip()}")

    assert not unexpected, "Command(s) failed:\n\n" + "\n\n".join(unexpected)
