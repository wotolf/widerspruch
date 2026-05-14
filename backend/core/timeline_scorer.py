"""Timeline Scorer — updates support_score of timeline events based on player actions."""
from __future__ import annotations

import re
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import TimelineEvent

log = structlog.get_logger()

_STOPWORDS = frozenset({
    # Deutsch
    "der", "die", "das", "ein", "eine", "einem", "einer", "eines", "und", "in",
    "zu", "von", "den", "dem", "mit", "ist", "im", "auf", "an", "für", "ich",
    "du", "er", "sie", "es", "wir", "ihr", "nicht", "auch", "aber", "bei",
    "als", "nach", "wie", "noch", "oder", "wenn", "wird", "war", "hat",
    "sein", "haben", "dann", "aus", "zum", "zur", "am", "diesem", "diese",
    "dieser", "dieses", "einen", "sich", "wird", "wurde", "wurden",
    # Englisch
    "the", "a", "an", "and", "of", "in", "to", "is", "it", "at", "by", "for",
    "on", "that", "was", "are", "be", "with", "as",
})

_DELTAS: dict[str, float] = {
    "spur": 0.03,
    "befragen": 0.05,
    "note": 0.02,
}


def _tokenize(text: str) -> set[str]:
    tokens = re.split(r"[^a-zäöüß]+", text.lower())
    return {t for t in tokens if len(t) > 2 and t not in _STOPWORDS}


class TimelineScorer:
    async def score_action(
        self,
        case_id: UUID,
        action_type: str,
        context: str,
        session: AsyncSession,
    ) -> None:
        delta = _DELTAS.get(action_type, 0.02)
        context_tokens = _tokenize(context)
        if not context_tokens:
            return

        events = list(await session.scalars(
            select(TimelineEvent).where(TimelineEvent.case_id == case_id)
        ))
        if not events:
            return

        scored = sorted(
            ((len(_tokenize(ev.description) & context_tokens), ev) for ev in events),
            key=lambda x: x[0],
            reverse=True,
        )

        for overlap, ev in scored[:2]:
            if overlap == 0:
                break
            ev.support_score = min(1.0, ev.support_score + delta)
            log.debug(
                "timeline_scorer_updated",
                event_id=str(ev.id),
                action_type=action_type,
                overlap=overlap,
                new_score=ev.support_score,
            )
