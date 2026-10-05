"""XP and rank rules. The single source of truth for the game economy (FR-54).

Everything here is pure: no database, no HTTP. Services call these functions.
"""

from dataclasses import dataclass

XP_PER_VOTE = 10
XP_PER_POST = 25


@dataclass(frozen=True)
class Rank:
    key: str
    name: str
    min_xp: int


# Lowest to highest. A user holds a rank from exactly its min_xp.
RANKS: tuple[Rank, ...] = (
    Rank("bronze", "Bronze Verifier", 0),
    Rank("silver", "Silver Verifier", 100),
    Rank("gold", "Gold Verifier", 300),
    Rank("platinum", "Platinum Verifier", 700),
    Rank("palladium", "Palladium Verifier", 1500),
)


def rank_for_xp(xp: int) -> Rank:
    if xp < 0:
        raise ValueError("xp cannot be negative")
    current = RANKS[0]
    for rank in RANKS:
        if xp >= rank.min_xp:
            current = rank
    return current


def next_rank(xp: int) -> Rank | None:
    current = rank_for_xp(xp)
    index = RANKS.index(current)
    return RANKS[index + 1] if index + 1 < len(RANKS) else None


def progress_to_next(xp: int) -> float:
    """Fraction (0..1) of the way from the current rank to the next. 1.0 at max rank."""
    current = rank_for_xp(xp)
    upcoming = next_rank(xp)
    if upcoming is None:
        return 1.0
    return (xp - current.min_xp) / (upcoming.min_xp - current.min_xp)
