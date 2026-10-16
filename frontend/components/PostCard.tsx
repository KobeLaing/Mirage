"use client";

import Link from "next/link";
import { useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/format";
import type { Post, VoteState } from "@/lib/types";
import { Avatar } from "./Avatar";
import { CommentSection } from "./CommentSection";
import { TrashIcon } from "./icons";
import { PostMedia } from "./PostMedia";
import { RankBadge, RANK_STYLES } from "./RankBadge";
import { ReactionBar } from "./ReactionBar";
import { VoteButtons } from "./VoteButtons";

// Mirrors XP_PER_POST in backend/app/progression.py (only used for this message).
const XP_PER_POST = 20;

interface PostCardProps {
  post: Post;
  onDeleted?: (postId: number) => void;
  label?: React.ReactNode; // e.g. "Voted AI" on the profile activity list
}

export function PostCard({ post: initial, onDeleted, label }: PostCardProps) {
  const { userId } = useAuth();
  const [post, setPost] = useState(initial);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isMine = userId === post.author.id;

  async function remove() {
    if (userId == null || !window.confirm(`Delete this post? Its ${XP_PER_POST} XP will be removed.`)) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deletePost(post.id);
      onDeleted?.(post.id);
    } catch (err) {
      setError(errorMessage(err));
      setDeleting(false);
    }
  }

  // Blind Mode: after voting, the server will now send the counts, caption and
  // comments it was withholding (or hide them again if the vote was removed).
  // Re-fetch the post rather than guess, so the server stays the only judge
  // of what this user may see.
  function onVoted(state: VoteState) {
    if ((state.votes === null) !== post.blind) {
      api.post(post.id).then(setPost).catch(() => undefined);
    }
  }

  const author = post.author;
  const alt = post.caption ? `Post by ${author.display_name}: ${post.caption}` : `Post by ${author.display_name}`;

  return (
    <article className="rounded-2xl bg-navy-800 p-3.5 ring-1 ring-navy-700" aria-label={`Post by ${author.display_name}`}>
      <header className="flex items-center gap-3">
        <Link href={`/users/${author.id}`} className="shrink-0 rounded-full">
          <Avatar avatarId={author.avatar_id} size={38} />
        </Link>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <Link href={`/users/${author.id}`} className="truncate font-semibold text-ink hover:underline">
              {author.display_name}
            </Link>
            <RankBadge rank={author.rank} size={20} />
          </div>
          <p className="text-xs text-muted">
            {RANK_STYLES[author.rank].name} · <time dateTime={post.created_at}>{timeAgo(post.created_at)}</time>
          </p>
        </div>
        {label}
        {isMine && onDeleted && (
          <button
            type="button"
            onClick={remove}
            disabled={deleting}
            className="rounded-lg p-2 text-faint hover:bg-navy-700 hover:text-danger disabled:opacity-40"
            aria-label="Delete post"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        )}
      </header>

      {/* Captions are rendered as plain text, never as HTML (SR-10). Blind Mode
          withholds them until you vote (the server sends null). */}
      {post.caption && <p className="mt-2.5 whitespace-pre-wrap break-words text-sm text-ink">{post.caption}</p>}

      <div className="mt-2.5">
        <PostMedia media={post.media} alt={alt} />
      </div>

      {/* Voting is the main action; reactions sit quietly to the side. In Blind
          Mode, only the vote buttons show until you vote. */}
      <footer className="mt-3 flex items-start justify-between gap-3">
        <VoteButtons postId={post.id} votes={post.votes} myVote={post.my_vote} onVoted={onVoted} />
        {post.reactions && (
          <ReactionBar key={`r${post.blind}`} postId={post.id} reactions={post.reactions} myReaction={post.my_reaction} />
        )}
      </footer>

      {post.blind ? (
        <p className="mt-2 text-xs text-faint">Blind Mode: vote to reveal the results and comments.</p>
      ) : (
        post.comment_count !== null && <CommentSection key={`c${post.blind}`} postId={post.id} count={post.comment_count} />
      )}

      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </article>
  );
}
