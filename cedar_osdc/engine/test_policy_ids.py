"""Every policy carries a unique @id.

The corpus and the command line name a case's `reason` and `errors`
by a policy's `@id`, mapping the name to the position Cedar itself
reports. If a policy had no `@id`, or two policies in the same file
shared one, that mapping would silently misalign a case onto the
wrong policy. This is the guardrail: for every policies.cedar under
usecases/*/ and under the nine top-level iteration directories, the
count of permit/forbid statements must equal the count of @id
annotations, and the ids collected from one file must all be
distinct.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

ITERATIONS = ("bola-reads", "bola-writes", "field-reads", "field-writes",
              "function-level", "on-behalf-of", "contract", "row-filtering", "gateway")

POLICY_FILES = sorted(REPO.glob("usecases/*/policies.cedar")) + [
    REPO / name / "policies.cedar" for name in ITERATIONS
]

POLICY = re.compile(r"^\s*(?:permit|forbid)\(", re.M)
ID = re.compile(r'@id\("([^"]+)"\)')


@pytest.mark.parametrize("path", POLICY_FILES, ids=[str(p.relative_to(REPO)) for p in POLICY_FILES])
def test_every_policy_has_a_unique_id(path):
    assert path.is_file(), f"{path} does not exist"
    text = path.read_text()
    policies = POLICY.findall(text)
    ids = ID.findall(text)
    assert len(ids) == len(policies), (
        f"{path.relative_to(REPO)}: {len(policies)} policies but {len(ids)} @id annotations"
    )
    assert len(set(ids)) == len(ids), f"{path.relative_to(REPO)}: duplicate @id among {ids}"
