"""Quoted-policy check: every Cedar policy a learning page shows is a
verbatim copy of a policy in the tree.

The pages quote policies and guardrails by ``@id``; a quote that drifts
from the file it came from teaches the wrong policy. For every
``<pre><code class="lang-cedar">`` block under ``learn/`` and in
``README.md`` that begins with ``@id(``, the block's text, whitespace
normalized, must appear in ``policies.cedar`` or a ``guardrails/*.cedar``
file of some use case.

Run directly with ``uv run python -m cedar_odcs.checks.quotes``, or
through ``test_quotes.py``.
"""

from __future__ import annotations

import html as _html
import re
import sys
from dataclasses import dataclass
from pathlib import Path

CEDAR_BLOCK_RE = re.compile(
    r'<pre[^>]*>\s*<code class="lang-cedar">(.*?)</code>\s*</pre>', re.S | re.I
)
FENCED_CEDAR_RE = re.compile(r"```cedar\n(.*?)```", re.S)
ID_RE = re.compile(r'@id\("([^"]+)"\)')


def normalize(text: str) -> str:
    return " ".join(text.split())


def quoted_policies(text: str, suffix: str) -> list[str]:
    """Every policy block in text that begins with an @id annotation."""
    pattern = CEDAR_BLOCK_RE if suffix == ".html" else FENCED_CEDAR_RE
    blocks = []
    for block in pattern.findall(text):
        block = _html.unescape(block) if suffix == ".html" else block
        if block.lstrip().startswith("@id("):
            blocks.append(block)
    return blocks


def policy_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for usecase in sorted((root / "usecases").iterdir()):
        if not (usecase / "policies.cedar").is_file():
            continue
        files.append(usecase / "policies.cedar")
        files.extend(sorted((usecase / "guardrails").glob("*.cedar")))
    return files


def quote_sources(root: Path) -> list[Path]:
    paths = [root / "README.md"]
    paths.extend(sorted((root / "learn").glob("*.html")))
    return [p for p in paths if p.is_file()]


@dataclass(frozen=True)
class Drift:
    source: Path
    policy_id: str

    def __str__(self) -> str:
        return f"{self.source}: quoted {self.policy_id!r} matches no policy or guardrail verbatim"


def check(root: Path) -> tuple[int, list[Drift]]:
    """The number of quotes checked, and every one that drifted."""
    corpus = " ".join(normalize(p.read_text(encoding="utf-8")) for p in policy_files(root))
    drifted: list[Drift] = []
    count = 0
    for source in quote_sources(root):
        text = source.read_text(encoding="utf-8")
        for block in quoted_policies(text, source.suffix):
            count += 1
            if normalize(block) not in corpus:
                match = ID_RE.search(block)
                drifted.append(Drift(source.relative_to(root), match.group(1) if match else "?"))
    return count, drifted


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    count, drifted = check(root)
    for d in drifted:
        print(d)
    print(f"{count} quoted policies, {len(drifted)} drifted")
    return 1 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
