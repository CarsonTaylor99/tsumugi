"""The EngineAdapter contract (docs/02). A Protocol, not an ABC:
structural typing keeps adapters decoupled and pyright --strict still
checks conformance."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator, Protocol

from tsumugi.core.models import (
    EngineProbe,
    EngineTextCaps,
    RoundTripResult,
    TextUnit,
    Workspace,
)


class EngineAdapter(Protocol):
    name: str
    caps: EngineTextCaps

    def probe(self, game_dir: Path) -> EngineProbe | None:
        """Confidence + evidence, or None if this clearly isn't our engine."""
        ...

    def extract(self, ws: Workspace) -> Iterator[TextUnit]:
        """Units with placeholders masked. Must not modify game_dir."""
        ...

    def inject(self, ws: Workspace, units: Iterable[TextUnit]) -> None:
        """Write patched script files under ws.patched_dir(), mirroring
        relative paths. A unit with target_text=None injects its source
        (the identity path Gate A exercises)."""
        ...

    def verify_round_trip(self, ws: Workspace) -> RoundTripResult:
        """Hard rule 2: Gate A (identity) + Gate B (expansion)."""
        ...
