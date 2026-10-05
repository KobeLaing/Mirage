"""Turns Post rows into PostOut views with counts, in a fixed number of queries.

For any page size: 1 query for the posts (+ authors via JOIN, done by the
caller) and 2 aggregate queries for counts, plus 2 for the viewer's own vote
and reaction when a viewer is known. No per-post queries (NFR-4).
"""

from sqlalchemy.orm import Session

from app.db.models import Post
from app.repositories import post_repo, reaction_repo, vote_repo
from app.schemas.posts import MediaOut, PostOut, ReactionCounts, VoteCounts
from app.services.user_service import to_summary
from app.storage.base import MediaStorage


def build(db: Session, storage: MediaStorage, posts: list[Post], viewer_id: int | None) -> list[PostOut]:
    ids = [p.id for p in posts]
    votes = post_repo.vote_counts(db, ids)
    reactions = post_repo.reaction_counts(db, ids)
    my_votes = vote_repo.values_for_user(db, viewer_id, ids) if viewer_id else {}
    my_reactions = reaction_repo.kinds_for_user(db, viewer_id, ids) if viewer_id else {}
    return [
        PostOut(
            id=p.id,
            author=to_summary(p.author),
            caption=p.caption,
            media=MediaOut(
                kind=p.media_kind,
                url=storage.url_for(p.media_key),
                mime_type=p.mime_type,
                width=p.width,
                height=p.height,
            ),
            votes=VoteCounts(ai=votes[p.id].get("AI", 0), real=votes[p.id].get("REAL", 0)),
            reactions=ReactionCounts(**reactions[p.id]),
            my_vote=my_votes.get(p.id),
            my_reaction=my_reactions.get(p.id),
            created_at=p.created_at,
        )
        for p in posts
    ]
