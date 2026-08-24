"""bible.draft: aggregate map observations + mined terms into the
human-editable draft bible (YAML, docs/03 layout). Deterministic — the
LLM reduce pass for conflict resolution comes later; here disagreements
are *surfaced*, never silently resolved (docs/03 pass C rule)."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import yaml

from tsumugi.bible.mapper import WindowObservation
from tsumugi.core.store import ProjectStore


def _slug(name: str) -> str:
    s = re.sub(r"[^\w]", "_", name)
    return s or "unknown"


def build_draft(store: ProjectStore, out_dir: Path) -> dict[str, int]:
    """Write bible/cast/*.yaml, glossary.yaml, style.yaml. Returns counts."""
    first_person: dict[str, Counter[str]] = {}
    register: dict[str, Counter[str]] = {}
    gender: dict[str, Counter[str]] = {}
    notes: dict[str, Counter[str]] = {}
    llm_terms: Counter[str] = Counter()
    windows = 0

    for _scene, payload in store.observations():
        windows += 1
        obs = WindowObservation.model_validate(json.loads(payload))
        for c in obs.characters:
            name = c.name_ja.strip()
            if not name:
                continue
            for field, bucket in (
                (c.first_person, first_person),
                (c.speech_style, register),
                (c.gender_evidence, gender),
                (c.notes, notes),
            ):
                if field:
                    bucket.setdefault(name, Counter())[field.strip()] += 1
        for t in obs.terms:
            llm_terms[t.strip()] += 1

    speakers = {
        s: n for s, n in store.stats().speakers.items()
    }  # ground truth from extraction

    cast_dir = out_dir / "cast"
    cast_dir.mkdir(parents=True, exist_ok=True)
    for name, line_count in speakers.items():
        fp = first_person.get(name, Counter())
        reg = register.get(name, Counter())
        gen = gender.get(name, Counter())
        conflicts: list[str] = []
        if len(fp) > 1:
            conflicts.append(f"first_person disputed: {dict(fp.most_common(3))}")
        card = {
            "id": _slug(name),
            "name_ja": name,
            "name_en": "TODO",
            "pronouns": "TODO — evidence: "
            + (gen.most_common(1)[0][0] if gen else "none collected"),
            "lines": line_count,
            "first_person": fp.most_common(1)[0][0] if fp else None,
            "register": "; ".join(k for k, _ in reg.most_common(2)) or None,
            "speech_notes": [k for k, _ in notes.get(name, Counter()).most_common(3)],
            "conflicts": conflicts,
            "status": "draft",
        }
        (cast_dir / f"{_slug(name)}.yaml").write_text(
            yaml.safe_dump(card, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    mined = store.terms(limit=150)
    glossary = [
        {
            "ja": term,
            "en": "TODO",
            "kind": kind,
            "count": count,
            "llm_flagged": term in llm_terms,
            "sample": sample,
        }
        for term, count, kind, sample in mined
        if kind != "speaker"
    ]
    (out_dir / "glossary.yaml").write_text(
        yaml.safe_dump(glossary, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    style = {
        "honorifics": "TODO: keep | drop | selective (suggest: keep — docs/09 Q4)",
        "name_order": "TODO: japanese | western",
        "quotes": "「」 -> “”",
        "sfx_policy": "TODO: translate | romanise | leave",
        "status": "draft — translation cannot start until approved (hard rule 5)",
    }
    (out_dir / "style.yaml").write_text(
        yaml.safe_dump(style, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    return {
        "windows": windows,
        "cast": len(speakers),
        "glossary": len(glossary),
    }
