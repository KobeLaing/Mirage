"""Voting and XP.

The rules:
- One vote per user per post. The database enforces it too, with a unique
  constraint, so even two simultaneous requests can't create two votes.
- Voting the same way again changes nothing, so double-clicks are harmless.
- Switching between AI and REAL moves your vote but doesn't change XP.
- Your first vote on a post earns XP_PER_VOTE; removing it takes that XP back,
  so voting and un-voting in a loop can't farm points.

Votes and XP are saved in one transaction, so if either fails, neither is
saved. This prevents users from getting XP for a vote that didn't count, or
losing a vote without getting its XP back.
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Post, User
from app.errors import NotFound
from app.progression import XP_PER_VOTE, rank_for_xp
from app.repositories import post_repo, user_repo, vote_repo
from app.schemas.votes import MyStanding, VoteCounts, VoteState
from app.services.blind_mode import is_hidden

log = logging.getLogger("mirage.votes")


def _require_post(db: Session, post_id: int) -> Post:
    post = post_repo.get(db, post_id)
    if post is None:
        raise NotFound("That post doesn't exist.")
    return post


def _state(db: Session, user: User, post: Post) -> VoteState:
    my_vote = vote_repo.values_for_user(db, user.id, [post.id]).get(post.id)
    xp = user_repo.current_xp(db, user.id)
    # Blind Mode: removing your vote hides the counts again (they're only
    # shown to people who have a vote on the post).
    if is_hidden(user, post.author_id, my_vote):
        votes = None
    else:
        counts = post_repo.vote_counts(db, [post.id])[post.id]
        votes = VoteCounts(ai=counts.get("AI", 0), real=counts.get("REAL", 0))
    return VoteState(post_id=post.id, my_vote=my_vote, votes=votes, me=MyStanding(xp=xp, rank=rank_for_xp(xp).key))


def set_vote(db: Session, user: User, post_id: int, value: str) -> VoteState:
    post = _require_post(db, post_id)
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
    return _state(db, user, post)


def remove_vote(db: Session, user: User, post_id: int) -> VoteState:
    post = _require_post(db, post_id)
    existing = vote_repo.get(db, user.id, post_id)
    if existing is not None:
        vote_repo.delete(db, existing)
        user_repo.add_xp(db, user.id, -XP_PER_VOTE)
        db.commit()
        log.info("vote.removed", extra={"post_id": post_id})
    return _state(db, user, post)
