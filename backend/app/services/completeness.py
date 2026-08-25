"""Deterministic onboarding profile completeness scoring (no LLM involvement).

Each of the five profile slots is worth 20 points. A slot counts as filled
only when it holds a non-empty value; ``pace_preference`` counts once it is a
valid :class:`~app.models.subject_profile.PacePreference`.
"""

from dataclasses import dataclass, field

from app.models.subject_profile import PacePreference, SubjectProfile

ONBOARDING_SLOTS = [
    "goal",
    "current_level",
    "background",
    "motivation",
    "pace_preference",
]

_POINTS_PER_SLOT = 20


@dataclass(frozen=True)
class CompletenessInfo:
    """Result snapshot describing how complete an onboarding profile is."""

    score: int
    filled_slots: list[str] = field(default_factory=list)
    missing_slots: list[str] = field(default_factory=list)


def _slot_is_filled(profile: SubjectProfile, slot: str) -> bool:
    """Return True when the given slot holds a meaningful value."""
    value = getattr(profile, slot)
    if slot == "pace_preference":
        return isinstance(value, PacePreference)
    return bool(value and value.strip())


def compute_completeness(profile: SubjectProfile | None) -> CompletenessInfo:
    """Compute the completeness score for a subject profile.

    Pure and deterministic - safe to call with ``None`` for subjects that have
    no profile row yet.
    """
    if profile is None:
        return CompletenessInfo(
            score=0,
            filled_slots=[],
            missing_slots=list(ONBOARDING_SLOTS),
        )

    filled_slots = [s for s in ONBOARDING_SLOTS if _slot_is_filled(profile, s)]
    missing_slots = [s for s in ONBOARDING_SLOTS if s not in filled_slots]
    score = len(filled_slots) * _POINTS_PER_SLOT

    return CompletenessInfo(
        score=min(score, 100),
        filled_slots=filled_slots,
        missing_slots=missing_slots,
    )
