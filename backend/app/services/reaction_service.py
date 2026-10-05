"""Reactions (FR-30..34): one per user per post, changeable, removable, no XP."""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import User
from app.errors import NotFound
from app.repositories import post_repo, reaction_repo
from app.schemas.posts import ReactionCounts
from app.schemas.votes import ReactionState

log = logging.getLogger("mirage.reactions")


def _require_post(db: Session, post_id: int) -> None:
    if post_repo.get(db, post_id) is None:
        raise NotFound("That post doesn't exist.")


def _state(db: Session, user_id: int, post_id: int) -> ReactionState:
    counts = post_repo.reaction_counts(db, [post_id])[post_id]
    return ReactionState(
        post_id=post_id,
        my_reaction=reaction_repo.kinds_for_user(db, user_id, [post_id]).get(post_id),
        reactions=ReactionCounts(**counts),
    )


def set_reaction(db: Session, user: User, post_id: int, kind: str) -> ReactionState:
    _require_post(db, post_id)
    for attempt in range(2):
        try:
            existing = reaction_repo.get(db, user.id, post_id)
            if existing is None:
                reaction_repo.create(db, user.id, post_id, kind)
            elif existing.kind != kind:
                reaction_repo.change(db, existing, kind)
            db.commit()
            break
        except IntegrityError:
            db.rollback()  # lost a race on uq_reactions_user_post; retry as an update
            if attempt == 1:
                raise
    log.info("reaction.set", extra={"post_id": post_id, "kind": kind})
    return _state(db, user.id, post_id)


def remove_reaction(db: Session, user: User, post_id: int) -> ReactionState:
    _require_post(db, post_id)
    existing = reaction_repo.get(db, user.id, post_id)
    if existing is not None:
        reaction_repo.delete(db, existing)
        db.commit()
        log.info("reaction.removed", extra={"post_id": post_id})
    return _state(db, user.id, post_id)
