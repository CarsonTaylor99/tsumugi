"""Extraction from KiriKiriZ compiled .scn scenarios (PSB).

Observed structure (real KAGEnvPlayer title, PSB v3 *.txt.scn):

  root: { name, hash, scenes: [ { label, title, texts, lines, nexts, … } ] }
  texts[i] = [ display_name | null,
               [ [ name_label | null, text, length ], … ],   # takes
               voice_info | null, flags, stage_state ]

The middle element holds the actual dialogue; multiple "takes" of one line
exist for state-dependent variants and are extracted as separate units.
Extract-only: writing PSB (offset/string-table rebuild) is Phase 6 work, so
no translated build is possible for .scn yet — the gates report this rather
than pretend otherwise (hard rule 2).
"""

from __future__ import annotations

import hashlib
from typing import Iterator

from tsumugi.core.models import TextUnit, UnitKind
from tsumugi.formats.kirikiri.psb import PsbError, PsbReader, PsbValue
from tsumugi.formats.kirikiri.tags import mask


def is_scenario_psb(root: PsbValue) -> bool:
    return isinstance(root, dict) and "scenes" in root


def extract_scn(raw: bytes, rel: str, ordinal_start: int) -> Iterator[TextUnit]:
    """TextUnits from one .scn. Raises PsbError on a malformed file."""
    root = PsbReader(raw).root()
    if not is_scenario_psb(root):
        raise PsbError(f"{rel}: PSB has no scenes — not a scenario file")
    assert isinstance(root, dict)
    scenes = root["scenes"]
    if not isinstance(scenes, list):
        raise PsbError(f"{rel}: scenes is not a list")

    ordinal = ordinal_start
    for si, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue
        texts = scene.get("texts")
        if not isinstance(texts, list):
            continue
        for ti, entry in enumerate(texts):
            if not isinstance(entry, list) or len(entry) < 2:
                continue
            display = entry[0] if isinstance(entry[0], str) else None
            takes = entry[1]
            if not isinstance(takes, list):
                continue
            for vi, take in enumerate(takes):
                if not isinstance(take, list) or len(take) < 2:
                    continue
                label = take[0] if isinstance(take[0], str) else None
                text = take[1]
                if not isinstance(text, str) or not text:
                    continue
                masked_result = mask(text)
                if masked_result is None:
                    continue  # unmaskable markup: leave untouched
                masked, placeholders = masked_result
                speaker = display or label
                digest = hashlib.sha256(masked.encode("utf-8")).hexdigest()
                ordinal += 1
                yield TextUnit(
                    id=f"{rel}:s{si}t{ti}v{vi}:{digest[:8]}",
                    source_text=masked,
                    placeholders=placeholders,
                    speaker=speaker,
                    kind=UnitKind.DIALOGUE if speaker else UnitKind.NARRATION,
                    file=rel,
                    offset=ordinal,  # no byte offset until the PSB writer exists
                    length=len(text),
                    ordinal=ordinal,
                    source_hash=digest,
                )
