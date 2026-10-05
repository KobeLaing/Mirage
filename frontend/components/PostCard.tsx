"use client";

import Link from "next/link";
import { useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useCurrentUser } from "@/lib/currentUser";
import { timeAgo } from "@/lib/format";
import type { Post } from "@/lib/types";
import { Avatar } from "./Avatar";
import { TrashIcon } from "./icons";
import { PostMedia } from "./PostMedia";
import { RankBadge, RANK_STYLES } from "./RankBadge";
import { ReactionBar } from "./ReactionBar";
import { VoteButtons } from "./VoteButtons";

interface PostCardProps {
  post: Post;
  onDeleted?: (postId: number) => void;
  label?: React.ReactNode; // e.g. "Voted AI" on the profile activity list
}

export function PostCard({ post, onDeleted, label }: PostCardProps) {
  const { userId } = useCurrentUser();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isMine = userId === post.author.id;

  async function remove() {
    if (userId == null || !window.confirm("Delete this post? Its 25 XP will be removed.")) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deletePost(userId, post.id);
      onDeleted?.(post.id);
    } catch (err) {
      setError(errorMessage(err));
      setDeleting(false);
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

      {/* Captions are rendered as plain text, never as HTML (SR-10). */}
      {post.caption && <p className="mt-2.5 whitespace-pre-wrap break-words text-sm text-ink">{post.caption}</p>}

      <div className="mt-2.5">
        <PostMedia media={post.media} alt={alt} />
      </div>

      {/* Voting is the main action; reactions sit quietly to the side. */}
      <footer className="mt-3 flex items-start justify-between gap-3">
        <VoteButtons postId={post.id} votes={post.votes} myVote={post.my_vote} />
        <ReactionBar postId={post.id} reactions={post.reactions} myReaction={post.my_reaction} />
      </footer>

      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </article>
  );
}
