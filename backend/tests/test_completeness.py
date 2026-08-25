"""Pure-function tests for deterministic completeness scoring (no DB)."""

import uuid

from app.models.subject_profile import (
    PacePreference,
    SubjectProfile,
    SubjectProfileStatus,
)
from app.services.completeness import (
    ONBOARDING_SLOTS,
    compute_completeness,
)


def _profile(**overrides: object) -> SubjectProfile:
    """Build an in-memory SubjectProfile with sensible defaults."""
    defaults: dict[str, object] = {
        "subject_id": uuid.uuid4(),
        "status": SubjectProfileStatus.ONBOARDING,
    }
    defaults.update(overrides)
    return SubjectProfile(**defaults)  # type: ignore[arg-type]


def test_none_profile_scores_zero() -> None:
    """A subject without a profile scores 0 with every slot missing."""
    info = compute_completeness(None)
    assert info.score == 0
    assert info.filled_slots == []
    assert info.missing_slots == ONBOARDING_SLOTS


def test_default_profile_only_pace_filled() -> None:
    """A fresh profile fills pace_preference (valid default) worth 20 points."""
    info = compute_completeness(_profile())
    assert info.score == 20
    assert info.filled_slots == ["pace_preference"]
    assert info.missing_slots == [
        "goal",
        "current_level",
        "background",
        "motivation",
    ]


def test_single_text_slot_adds_twenty() -> None:
    """Setting only the goal yields pace + goal = 40 points."""
    info = compute_completeness(_profile(goal="Pass FAANG interviews"))
    assert info.score == 40
    assert info.filled_slots == ["goal", "pace_preference"]
    assert info.missing_slots == ["current_level", "background", "motivation"]


def test_whitespace_only_slot_not_counted() -> None:
    """Whitespace-only values do not count as filled slots."""
    info = compute_completeness(_profile(goal="   ", background="\t\n"))
    assert info.score == 20
    assert info.filled_slots == ["pace_preference"]
    assert "goal" in info.missing_slots
    assert "background" in info.missing_slots


def test_full_profile_scores_hundred() -> None:
    """All five slots filled yields exactly 100 with nothing missing."""
    info = compute_completeness(
        _profile(
            goal="Build CLI tools",
            current_level="Beginner",
            background="Some Python",
            motivation="Career switch",
            pace_preference=PacePreference.INTENSE,
        )
    )
    assert info.score == 100
    assert info.filled_slots == ONBOARDING_SLOTS
    assert info.missing_slots == []


def test_missing_slots_ordered_like_onboarding_slots() -> None:
    """missing_slots preserves canonical ONBOARDING_SLOTS ordering."""
    info = compute_completeness(_profile(motivation="Fun"))
    assert info.missing_slots == ["goal", "current_level", "background"]
