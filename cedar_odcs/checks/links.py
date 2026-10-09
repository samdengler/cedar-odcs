"""Link and anchor checker for every Markdown and HTML page in the tree.

For every ``.md`` and ``.html`` file, every relative link (Markdown
``[text](path#frag)`` and HTML ``href="path#frag"`` / ``src="..."``)
must resolve to a file that exists, and a fragment must resolve to an
id in the target (an ``id="..."`` attribute in HTML, a heading's
GitHub-style slug in Markdown). Links starting with ``http:``,
``https:``, or ``mailto:`` are not checked, and a bare ``#frag`` is
checked against the file it appears in.

Run directly with ``uv run python -m cedar_odcs.checks.links``, or
through ``test_links.py``.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

EXCLUDED_DIR_NAMES = {".venv", ".beads", ".git", "__pycache__", "target"}

DOC_SUFFIXES = (".md", ".html")

MD_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
HTML_LINK_RE = re.compile(r'(?:href|src)="([^"]*)"')

SKIP_SCHEMES = ("http:", "https:", "mailto:")

HTML_ID_RE = re.compile(r'\bid="([^"]+)"')
ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class BrokenLink:
    source: Path
    line: int
    target: str
    reason: str

    def __str__(self) -> str:
        return f"{self.source}:{self.line} -> {self.target} ({self.reason})"


def iter_doc_files(root: Path):
    """Every .md and .html file under root, skipping the excluded dirs."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIR_NAMES)
        for name in sorted(filenames):
            if name.endswith(DOC_SUFFIXES):
                yield Path(dirpath) / name


def github_slug(heading: str) -> str:
    """Approximate GitHub's heading-to-anchor slug rule."""
    text = heading.strip().lower()
    # Markdown formatting and links inside a heading contribute their
    # text, not their syntax.
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_]", "", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    return text


def extract_md_anchors(text: str) -> set[str]:
    slugs: set[str] = set()
    seen_counts: dict[str, int] = {}
    for line in text.splitlines():
        match = ATX_HEADING_RE.match(line)
        if not match:
            continue
        heading = re.sub(r"\s+#+\s*$", "", match.group(2).strip())
        slug = github_slug(heading)
        if slug in seen_counts:
            seen_counts[slug] += 1
            slug = f"{slug}-{seen_counts[slug]}"
        else:
            seen_counts[slug] = 0
        slugs.add(slug)
    return slugs


def extract_html_anchors(text: str) -> set[str]:
    return set(HTML_ID_RE.findall(text))


@lru_cache(maxsize=None)
def _anchors_for(path: Path) -> frozenset[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return frozenset()
    if path.suffix == ".html":
        return frozenset(extract_html_anchors(text))
    if path.suffix == ".md":
        return frozenset(extract_md_anchors(text))
    return frozenset()


def _check_target(source: Path, target: str) -> str | None:
    """None if target resolves from source; otherwise the reason it does not."""
    if target.startswith("#"):
        frag = target[1:]
        if frag and frag not in _anchors_for(source):
            return f"fragment not found in {source.name}"
        return None

    path_part, _, frag = target.partition("#")
    if not path_part:
        return None

    resolved = (source.parent / path_part).resolve()
    if not resolved.is_file():
        return "target file does not exist"
    if not frag:
        return None
    if resolved.suffix not in DOC_SUFFIXES:
        # A fragment into a file type we don't parse for anchors (e.g. a
        # data file); the file existing is all we can check.
        return None
    if frag not in _anchors_for(resolved):
        return f"fragment not found in {path_part}"
    return None


def _targets_on_line(line: str) -> list[str]:
    targets = [m.group(1) for m in MD_LINK_RE.finditer(line)]
    targets += [m.group(1) for m in HTML_LINK_RE.finditer(line)]
    return targets


def scan_file(path: Path) -> list[BrokenLink]:
    broken: list[BrokenLink] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return broken
    for lineno, line in enumerate(text.splitlines(), start=1):
        for target in _targets_on_line(line):
            target = target.strip()
            if not target or target.startswith(SKIP_SCHEMES):
                continue
            reason = _check_target(path, target)
            if reason:
                broken.append(BrokenLink(path, lineno, target, reason))
    return broken


def find_broken_links(root: Path) -> list[BrokenLink]:
    broken: list[BrokenLink] = []
    for path in iter_doc_files(root):
        broken.extend(scan_file(path))
    return broken


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    broken = find_broken_links(root)
    if not broken:
        print("No broken links found.")
        return 0
    print(f"{len(broken)} broken link(s):")
    for link in broken:
        print(f"  {link}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
