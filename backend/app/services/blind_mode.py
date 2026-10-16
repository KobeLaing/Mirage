"""Blind Mode: vote first, see what everyone else thinks afterwards.

When a user turns Blind Mode on, a post they haven't voted on shows only its
image or video and the AI / Real buttons. Vote counts, reactions, the caption
and comments stay hidden until they vote, so the crowd can't sway them.

Why this is enforced on the server: if the API sent the counts and the
browser merely hid them, anyone could open the developer tools and read them
from the network response. So this one rule decides, on the server, what goes
into every response that carries post data (feed, single post, profile
activity, vote state, comments, reactions). Hidden values are never sent at
all; they come back as null.

A user's own posts are never hidden from them: they can't be biased about
their own upload.
"""

from app.db.models import User

HIDDEN_MESSAGE = "Vote on this post first. Blind Mode hides its comments and reactions until you do."


def is_hidden(viewer: User, author_id: int, my_vote: str | None) -> bool:
    """True if `viewer` must not see the crowd's opinion on this post yet."""
    return viewer.blind_mode and my_vote is None and author_id != viewer.id
