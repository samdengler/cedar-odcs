"""Command-line smoke test: extract, then run, every command line the
learning pages show.

The pages are the specification: each fenced ``sh`` block a reader is
told to run should actually run. This module finds those command
lines in the current source (README.md, learn/*.md, and
learn/hello/README.md), skips the ones that are syntax references
rather than something to type (they carry a placeholder like ``DIR``
or ``FILE``) or that are slow and covered elsewhere (``uv sync``,
``uv run pytest``), and runs the rest from the repository root.

The extractor is split by source type so a second source is adding a
function, not rewriting this one: ``extract_from_markdown`` today,
``extract_from_html`` once a later task (3f) gives the HTML pages the
same fenced examples and ``_command_sources`` is extended to include
them.

Run directly with ``uv run python -m cedar_osdc.checks.commands``, or
through ``test_commands.py``.
"""

from __future__ import annotations

import html as _html
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

COMMAND_PREFIXES = ("uv run cedar-osdc", "uv sync", "uv run pytest")

# Tokens that mark a line as a syntax reference rather than a command to
# run: a placeholder standing in for a real value.
PLACEHOLDER_TOKENS = (
    "DIR", "NAME", "...", "<", ">", "C.json", "T.json", "k=v", "KEY=VALUE", "FILE",
)

FENCED_SH_RE = re.compile(r"```sh\n(.*?)```", re.S)
HTML_PRE_CODE_RE = re.compile(r"<pre[^>]*>\s*<code[^>]*>(.*?)</code>\s*</pre>", re.S | re.I)

TRAILING_COMMENT_RE = re.compile(r"\s+#.*$")

DEFAULT_TIMEOUT = 120


def _join_continuations(raw_lines: list[str]) -> list[str]:
    """Backslash-continued physical lines become one logical line."""
    logical: list[str] = []
    buf = ""
    for raw in raw_lines:
        line = raw.strip()
        buf = f"{buf} {line}".strip() if buf else line
        if buf.endswith("\\"):
            buf = buf[:-1].rstrip()
            continue
        if buf:
            logical.append(buf)
        buf = ""
    if buf:
        logical.append(buf)
    return logical


def extract_from_markdown(text: str) -> list[str]:
    """Every logical line from every fenced ```sh block in text."""
    lines: list[str] = []
    for block in FENCED_SH_RE.findall(text):
        lines.extend(_join_continuations(block.splitlines()))
    return lines


def extract_from_html(text: str) -> list[str]:
    """Every logical line from every <pre><code> block in text.

    Not wired into a source yet; task 3f adds the HTML pages once they
    carry the same fenced examples as the Markdown ones, at which point
    a source using this belongs in _command_sources.
    """
    lines: list[str] = []
    for block in HTML_PRE_CODE_RE.findall(text):
        lines.extend(_join_continuations(_html.unescape(block).splitlines()))
    return lines


def _command_sources(root: Path) -> list[Path]:
    paths = [root / "README.md"]
    paths.extend(sorted((root / "learn").glob("*.md")))
    hello_readme = root / "learn" / "hello" / "README.md"
    if hello_readme not in paths:
        paths.append(hello_readme)
    return [p for p in paths if p.is_file()]


def _strip_comment(line: str) -> str:
    """Drop a trailing "  # explanation" — not part of the command."""
    return TRAILING_COMMENT_RE.sub("", line)


def is_command_line(line: str) -> bool:
    return line.startswith(COMMAND_PREFIXES)


def placeholder_in(line: str) -> str | None:
    for token in PLACEHOLDER_TOKENS:
        if token in line:
            return token
    return None


@dataclass
class Plan:
    to_run: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def plan_commands(root: Path) -> Plan:
    """Every command line to run, and every one skipped, with the reason.

    A command line already seen (the same text, verbatim, from any
    source) is folded into its first occurrence: this is what keeps
    "uv sync", extracted from more than one page, to a single run.
    """
    plan = Plan()
    seen: set[str] = set()
    for path in _command_sources(root):
        text = path.read_text(encoding="utf-8")
        for raw in extract_from_markdown(text):
            line = " ".join(_strip_comment(raw).split())
            if not is_command_line(line):
                continue
            if line in seen:
                continue
            seen.add(line)
            token = placeholder_in(line)
            if token:
                plan.skipped.append((line, f"placeholder token {token!r}"))
                continue
            if line.startswith("uv run pytest"):
                plan.skipped.append((line, "uv run pytest is slow and recursive; skipped here"))
                continue
            if line.startswith("uv run cedar-osdc prove"):
                plan.skipped.append((line, "prove runs the whole analysis; check.sh runs it once, outside pytest"))
                continue
            plan.to_run.append(line)
    return plan


@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        if self.timed_out:
            return False
        if self.returncode not in (0, 1):
            return False
        if "Traceback" in self.stderr:
            return False
        if "usage:" in self.stderr:
            return False
        return True

    @property
    def problem(self) -> str:
        if self.timed_out:
            return "timed out"
        if self.returncode not in (0, 1):
            return f"exit code {self.returncode}"
        if "Traceback" in self.stderr:
            return "Traceback in stderr"
        if "usage:" in self.stderr:
            return "usage: in stderr (argparse error, exit 2)"
        return ""


def run_command(command: str, root: Path, timeout: int = DEFAULT_TIMEOUT) -> CommandResult:
    try:
        proc = subprocess.run(
            command, shell=True, cwd=root, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command, -1, exc.stdout or "", exc.stderr or "", timed_out=True,
        )
    return CommandResult(command, proc.returncode, proc.stdout, proc.stderr)


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    plan = plan_commands(root)
    print(f"{len(plan.to_run)} command(s) to run, {len(plan.skipped)} skipped:")
    for line, reason in plan.skipped:
        print(f"  skip  {line}   ({reason})")

    failed: list[CommandResult] = []
    for line in plan.to_run:
        result = run_command(line, root)
        print(f"  {'ok  ' if result.ok else 'FAIL'}  {line}")
        if not result.ok:
            failed.append(result)

    if failed:
        print(f"\n{len(failed)} command(s) failed:")
        for result in failed:
            print(f"  {result.command}\n    {result.problem}\n    stderr: {result.stderr.strip()[:1000]}")
        return 1
    print("\nAll commands passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
