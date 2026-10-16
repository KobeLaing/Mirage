import pytest

from app import progression
from app.progression import next_rank, progress_to_next, rank_for_xp


def test_config_values():
    assert progression.XP_PER_VOTE == 10
    assert progression.XP_PER_POST == 20
    assert [(r.key, r.min_xp) for r in progression.RANKS] == [
        ("bronze", 0), ("silver", 100), ("gold", 300), ("platinum", 700), ("palladium", 1500),
    ]


@pytest.mark.parametrize(
    "xp, expected",
    [
        (0, "bronze"),
        (99, "bronze"),
        (100, "silver"),  # exactly on the threshold
        (101, "silver"),
        (299, "silver"),
        (300, "gold"),
        (699, "gold"),
        (700, "platinum"),
        (1499, "platinum"),
        (1500, "palladium"),
        (1_000_000, "palladium"),
    ],
)
def test_rank_boundaries(xp, expected):
    assert rank_for_xp(xp).key == expected


def test_rank_names():
    assert [r.name for r in progression.RANKS] == [
        "Bronze Verifier", "Silver Verifier", "Gold Verifier", "Platinum Verifier", "Palladium Verifier",
    ]


def test_negative_xp_rejected():
    with pytest.raises(ValueError):
        rank_for_xp(-1)


@pytest.mark.parametrize(
    "xp, expected_next",
    [(0, "silver"), (99, "silver"), (100, "gold"), (700, "palladium"), (1499, "palladium"), (1500, None)],
)
def test_next_rank(xp, expected_next):
    upcoming = next_rank(xp)
    assert (upcoming.key if upcoming else None) == expected_next


@pytest.mark.parametrize(
    "xp, fraction",
    [
        (0, 0.0),
        (50, 0.5),
        (100, 0.0),  # just reached silver: progress restarts
        (150, 0.25),  # seeded Silver user
        (600, 0.75),  # seeded Gold user
        (1100, 0.5),
        (1500, 1.0),  # max rank
        (9999, 1.0),
    ],
)
def test_progress(xp, fraction):
    assert progress_to_next(xp) == pytest.approx(fraction)
