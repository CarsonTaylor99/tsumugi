"""Validator 1: the placeholder contract (docs/05).

Phase 1 scope: multiset integrity and no invented sentinels. Position
anchoring and pair nesting land with Stage 5, when there is model output
to anchor.
"""

from __future__ import annotations

from collections import Counter

from tsumugi.core.models import TextUnit
from tsumugi.core.sentinels import sentinel_indices


def check_placeholder_contract(unit: TextUnit, candidate: str) -> list[str]:
    """Violations of the contract for `candidate` against `unit`.
    Empty list means the candidate passes. Messages carry values."""
    problems: list[str] = []
    expected = Counter(p.index for p in unit.placeholders)
    got = Counter(sentinel_indices(candidate))

    for idx in sorted(expected.keys() - got.keys()):
        problems.append(f"missing sentinel ⟦{idx}⟧ (expected {expected[idx]}x)")
    for idx in sorted(got.keys() - expected.keys()):
        problems.append(f"invented sentinel ⟦{idx}⟧ (not in source)")
    for idx in sorted(expected.keys() & got.keys()):
        if expected[idx] != got[idx]:
            problems.append(
                f"sentinel ⟦{idx}⟧ count {got[idx]}, expected {expected[idx]}"
            )
    return problems
