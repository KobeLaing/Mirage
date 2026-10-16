from app.schemas.common import StrictModel
from app.schemas.posts import ReactionCounts, ReactionKind, VoteCounts, VoteValue


class VoteIn(StrictModel):
    value: VoteValue


class ReactionIn(StrictModel):
    kind: ReactionKind


class MyStanding(StrictModel):
    xp: int
    rank: str


class VoteState(StrictModel):
    post_id: int
    my_vote: VoteValue | None
    votes: VoteCounts | None  # null when Blind Mode hides them (no vote on the post)
    me: MyStanding


class ReactionState(StrictModel):
    post_id: int
    my_reaction: ReactionKind | None
    reactions: ReactionCounts
