"""One-off rewrite: name a corpus case's `reason` and `errors` by the
policy's `@id`, not by its position in policies.cedar.

For each use case under usecases/*/, this builds the policyN -> @id
map from its policies.cedar, in file order, and rewrites every case
file under tests/test-cases/, replacing a positional id inside
`reason` or `errors` with the name. Only the quoted policyN tokens
inside those two arrays are touched; everything else in the file,
including whichever of the two pretty-printing styles the file
already uses, is left as it was. A newcomer's use case whose corpus
still reads by position runs this again the same way.

    uv run python -m cedar_osdc.engine.rename_reasons
"""

import re
import sys
from pathlib import Path

from cedar_osdc.engine.corpus import case_files, policy_names

REPO = Path(__file__).resolve().parents[2]

# "reason": [ ... ] or "errors": [ ... ], however the array is broken
# across lines; the arrays hold only string literals, so this never
# has to worry about nested brackets.
_ARRAY = re.compile(r'"(reason|errors)":\s*\[([^\]]*)\]', re.S)
_POSITION = re.compile(r'"policy(\d+)"')


def rewrite(root: Path) -> int:
    """Rewrite one use case's case files in place; return how many
    positional ids were replaced with names."""
    names = policy_names((root / "policies.cedar").read_text())
    changed = 0

    def replace_array(match: re.Match) -> str:
        nonlocal changed

        def replace_position(id_match: re.Match) -> str:
            nonlocal changed
            position = f"policy{id_match.group(1)}"
            name = names.get(position, position)
            if name != position:
                changed += 1
            return f'"{name}"'

        key, inner = match.group(1), match.group(2)
        return f'"{key}": [{_POSITION.sub(replace_position, inner)}]'

    for spec_file in case_files(root):
        text = spec_file.read_text()
        rewritten = _ARRAY.sub(replace_array, text)
        if rewritten != text:
            spec_file.write_text(rewritten)
    return changed


def main() -> int:
    total = 0
    for policies_file in sorted(REPO.glob("usecases/*/policies.cedar")):
        use_case = policies_file.parent
        n = rewrite(use_case)
        print(f"{use_case.relative_to(REPO)}: {n} reason/errors entries renamed")
        total += n
    print(f"{total} entries renamed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
