"""Turns Post rows into PostOut views with counts, in a fixed number of queries.

For any page size: 1 query for the posts (+ authors via JOIN, done by the
caller), 3 aggregate queries for counts (votes, reactions, comments), and 2
for the viewer's own vote and reaction. No per-post queries (NFR-4).

This is also where Blind Mode is applied to every response that lists posts:
for a post the viewer hasn't voted on yet, the counts, caption and comment
count are left out of the response entirely (see blind_mode.py).
"""

from sqlalchemy.orm import Session

from app.db.models import Post, User
from app.repositories import comment_repo, post_repo, reaction_repo, vote_repo
from app.schemas.posts import MediaOut, PostOut, ReactionCounts, VoteCounts
from app.services.blind_mode import is_hidden
from app.services.user_service import to_summary
from app.storage.base import MediaStorage


def build(db: Session, storage: MediaStorage, posts: list[Post], viewer: User) -> list[PostOut]:
    ids = [p.id for p in posts]
    votes = post_repo.vote_counts(db, ids)
    reactions = post_repo.reaction_counts(db, ids)
    comments = comment_repo.counts(db, ids)
    my_votes = vote_repo.values_for_user(db, viewer.id, ids)
    my_reactions = reaction_repo.kinds_for_user(db, viewer.id, ids)

    views = []
    for p in posts:
        hidden = is_hidden(viewer, p.author_id, my_votes.get(p.id))
        views.append(
            PostOut(
                id=p.id,
                author=to_summary(p.author),
                media=MediaOut(
                    kind=p.media_kind,
                    url=storage.url_for(p.media_key),
                    mime_type=p.mime_type,
                    width=p.width,
                    height=p.height,
                ),
                my_vote=my_votes.get(p.id),
                created_at=p.created_at,
                blind=hidden,
                # Everything below is the crowd's opinion (or could hint at the
                # answer), so Blind Mode withholds it until the viewer votes.
                caption=None if hidden else p.caption,
                votes=None if hidden else VoteCounts(ai=votes[p.id].get("AI", 0), real=votes[p.id].get("REAL", 0)),
                reactions=None if hidden else ReactionCounts(**reactions[p.id]),
                my_reaction=None if hidden else my_reactions.get(p.id),
                comment_count=None if hidden else comments[p.id],
            )
        )
    return views
