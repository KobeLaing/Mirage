"""Voting rules (FR-20..24, FR-52) and the vote/XP transaction (NFR-3).

- One vote per user per post (also enforced by uq_votes_user_post).
- Same vote again: no change (idempotent).
- Switching AI <-> REAL: XP unchanged.
- First vote: +XP_PER_VOTE. Removing a vote: -XP_PER_VOTE. Removing nothing: no change.
- The vote row and the XP change commit together or not at all.
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import User
from app.errors import NotFound
from app.progression import XP_PER_VOTE, rank_for_xp
from app.repositories import post_repo, user_repo, vote_repo
from app.schemas.votes import MyStanding, VoteCounts, VoteState

log = logging.getLogger("mirage.votes")


def _require_post(db: Session, post_id: int) -> None:
    if post_repo.get(db, post_id) is None:
        raise NotFound("That post doesn't exist.")


def _state(db: Session, user_id: int, post_id: int) -> VoteState:
    counts = post_repo.vote_counts(db, [post_id])[post_id]
    xp = user_repo.current_xp(db, user_id)
    return VoteState(
        post_id=post_id,
        my_vote=vote_repo.values_for_user(db, user_id, [post_id]).get(post_id),
        votes=VoteCounts(ai=counts.get("AI", 0), real=counts.get("REAL", 0)),
        me=MyStanding(xp=xp, rank=rank_for_xp(xp).key),
    )


def set_vote(db: Session, user: User, post_id: int, value: str) -> VoteState:
    _require_post(db, post_id)
    for attempt in range(2):
        try:
            existing = vote_repo.get(db, user.id, post_id)
            if existing is None:
                vote_repo.create(db, user.id, post_id, value)
                user_repo.add_xp(db, user.id, XP_PER_VOTE)
                outcome = "cast"
            elif existing.value != value:
                vote_repo.change(db, existing, value)
                outcome = "switched"
            else:
                outcome = "unchanged"
            db.commit()
            break
        except IntegrityError:
            # A concurrent request inserted the same (user, post) first. The unique
            # constraint stopped a duplicate; roll back (undoing our +XP too) and
            # re-run against the row that won, which takes the update/no-op path.
            db.rollback()
            if attempt == 1:
                raise
    log.info("vote.set", extra={"post_id": post_id, "value": value, "outcome": outcome})
    return _state(db, user.id, post_id)


def remove_vote(db: Session, user: User, post_id: int) -> VoteState:
    _require_post(db, post_id)
    existing = vote_repo.get(db, user.id, post_id)
    if existing is not None:
        vote_repo.delete(db, existing)
        user_repo.add_xp(db, user.id, -XP_PER_VOTE)
        db.commit()
        log.info("vote.removed", extra={"post_id": post_id})
    return _state(db, user.id, post_id)
