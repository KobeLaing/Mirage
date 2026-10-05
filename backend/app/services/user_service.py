import logging

from sqlalchemy.orm import Session

from app.db.models import User
from app.errors import NotFound
from app.progression import Rank, next_rank, progress_to_next, rank_for_xp
from app.repositories import user_repo
from app.schemas.users import Profile, RankOut, UserSummary

log = logging.getLogger("mirage.users")


def _rank_out(rank: Rank | None) -> RankOut | None:
    return RankOut(key=rank.key, name=rank.name, min_xp=rank.min_xp) if rank else None


def to_summary(user: User) -> UserSummary:
    return UserSummary(
        id=user.id,
        handle=user.handle,
        display_name=user.display_name,
        avatar_id=user.avatar_id,
        rank=rank_for_xp(user.xp).key,
    )


def to_profile(user: User) -> Profile:
    return Profile(
        id=user.id,
        handle=user.handle,
        display_name=user.display_name,
        avatar_id=user.avatar_id,
        xp=user.xp,
        rank=_rank_out(rank_for_xp(user.xp)),
        next_rank=_rank_out(next_rank(user.xp)),
        progress=round(progress_to_next(user.xp), 4),
    )


def resolve(db: Session, user_id: int) -> User | None:
    """Used only by the identity dependency."""
    return user_repo.get(db, user_id)


def list_users(db: Session) -> list[UserSummary]:
    return [to_summary(u) for u in user_repo.list_all(db)]


def get_profile(db: Session, user_id: int) -> Profile:
    user = user_repo.get(db, user_id)
    if user is None:
        raise NotFound("That user doesn't exist.")
    db.refresh(user)  # XP may have been changed by an atomic UPDATE in this session
    return to_profile(user)


def set_avatar(db: Session, user: User, avatar_id: int) -> Profile:
    # `user` is always the authenticated user: there is no way to target someone else.
    user_repo.set_avatar(db, user, avatar_id)
    db.commit()
    log.info("user.avatar_changed", extra={"avatar_id": avatar_id})
    return get_profile(db, user.id)
