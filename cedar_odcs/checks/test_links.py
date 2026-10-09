"""pytest wrapper over cedar_odcs/checks/links.py.

Collects every broken relative link and fragment in the tree's
Markdown and HTML pages into one assertion, so a run names every
break at once rather than stopping at the first.
"""

from pathlib import Path

from cedar_odcs.checks.links import find_broken_links

REPO_ROOT = Path(__file__).resolve().parents[2]

# Links that are broken on the current tree today. Task 3a (this task)
# lists them rather than editing the pages that carry them, since a
# later docs task rewrites those pages anyway. Empty today: the scan
# below finds no broken links in the current layout.
ALLOWED_BROKEN: set[tuple[str, str]] = set()


def test_no_broken_links():
    broken = find_broken_links(REPO_ROOT)
    unexpected = [
        link
        for link in broken
        if (str(link.source.relative_to(REPO_ROOT)), link.target) not in ALLOWED_BROKEN
    ]
    assert not unexpected, "Broken link(s) found:\n" + "\n".join(
        str(link) for link in unexpected
    )
