"""pytest wrapper over cedar_osdc/checks/commands.py.

Runs every command line the learning pages show (minus placeholders
and the two slow, recursive ones) from the repository root, and
requires each to exit 0 or 1 with no Traceback and no argparse
"usage:" in stderr.
"""

from pathlib import Path

from cedar_osdc.checks.commands import plan_commands, run_command

REPO_ROOT = Path(__file__).resolve().parents[2]

# Commands that are broken on the current tree today. README.md's
# "## Command line" example for reservations writes the caller and
# response paths as bare filenames ("agent.json", "record.json"), as
# if the repository root were the use case directory; core/cli.py's
# _caller() and cmd_dry_run() read --caller and --response relative to
# the current directory, so both raise FileNotFoundError (a Traceback)
# when run from the repository root as literally shown. Task 3a lists
# this rather than editing the page (a later docs task, 3b/3d, rewrites
# it); recorded here so the test stays green and the debt stays
# visible.
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
