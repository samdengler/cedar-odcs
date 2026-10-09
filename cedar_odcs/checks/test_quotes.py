"""pytest wrapper over cedar_odcs/checks/quotes.py: every policy the
pages quote by @id is a verbatim copy of one in the tree."""

from pathlib import Path

from cedar_odcs.checks.quotes import check

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_quoted_policies_match_the_tree():
    count, drifted = check(REPO_ROOT)
    assert count >= 5, "expected the learning pages to quote policies"
    assert not drifted, "Quoted policies drifted:\n" + "\n".join(map(str, drifted))
