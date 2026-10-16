"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { Comment } from "@/lib/types";
import { Avatar } from "./Avatar";
import { CommentIcon, TrashIcon } from "./icons";
import { RankBadge } from "./RankBadge";

const MAX_COMMENT = 500;

/**
 * Comments under a post. Collapsed by default so the feed stays focused on
 * voting; opening it loads the comments on demand.
 *
 * Comment text is rendered as a plain React text node, never as HTML, so a
 * comment like "<script>…</script>" shows up as those literal characters.
 */
export function CommentSection({ postId, count }: { postId: number; count: number }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Comment[] | null>(null);
  const [total, setTotal] = useState(count);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const listId = useId();
  const inputId = useId();

  useEffect(() => {
    if (!open || items !== null) return;
    const controller = new AbortController();
    api
      .comments(postId, controller.signal)
      .then((list) => {
        setItems(list.items);
        setTotal(list.items.length);
      })
      .catch((err) => !controller.signal.aborted && setLoadError(errorMessage(err)));
    return () => controller.abort();
  }, [open, items, postId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !draft.trim()) return;
    setBusy(true);
    setFormError(null);
    try {
      const created = await api.addComment(postId, draft);
      setItems((prev) => [...(prev ?? []), created]);
      setTotal((n) => n + 1);
      setDraft("");
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(comment: Comment) {
    if (!window.confirm("Delete your comment?")) return;
    try {
      await api.deleteComment(comment.id);
      setItems((prev) => (prev ?? []).filter((c) => c.id !== comment.id));
      setTotal((n) => Math.max(0, n - 1));
    } catch (err) {
      setFormError(errorMessage(err));
    }
  }

  return (
    <div className="mt-3 border-t border-navy-700 pt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={listId}
        className="flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-semibold text-muted hover:bg-navy-700 hover:text-ink"
      >
        <CommentIcon className="h-4 w-4" />
        {total === 0 ? "Comment" : `${total} ${total === 1 ? "comment" : "comments"}`}
      </button>

      <div id={listId} hidden={!open} className="mt-2 space-y-3">
        {loadError && (
          <p role="alert" className="text-sm text-danger">
            {loadError}
          </p>
        )}
        {open && items === null && !loadError && <p className="text-xs text-faint">Loading comments…</p>}
        {items && items.length > 0 && (
          <ul className="space-y-3">
            {items.map((c) => (
              <li key={c.id} className="flex gap-2.5">
                <Link href={`/users/${c.author.id}`} className="shrink-0 rounded-full">
                  <Avatar avatarId={c.author.avatar_id} size={30} />
                </Link>
                <div className="min-w-0 flex-1 rounded-xl bg-navy-900 px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    <Link href={`/users/${c.author.id}`} className="truncate text-sm font-semibold text-ink hover:underline">
                      {c.author.display_name}
                    </Link>
                    <RankBadge rank={c.author.rank} size={16} />
                    <time dateTime={c.created_at} className="text-xs text-faint">
                      {timeAgo(c.created_at)}
                    </time>
                    {c.mine && (
                      <button
                        type="button"
                        onClick={() => remove(c)}
                        className="ml-auto rounded p-1 text-faint hover:text-danger"
                        aria-label="Delete your comment"
                      >
                        <TrashIcon className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                  <p className="mt-0.5 whitespace-pre-wrap break-words text-sm text-ink">{c.body}</p>
                </div>
              </li>
            ))}
          </ul>
        )}

        <form onSubmit={submit} className="flex items-end gap-2">
          <label htmlFor={inputId} className="sr-only">
            Write a comment
          </label>
          <textarea
            id={inputId}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={MAX_COMMENT}
            rows={1}
            placeholder="Add a comment"
            className="min-h-9 flex-1 resize-y rounded-xl bg-navy-900 px-3 py-1.5 text-sm text-ink placeholder:text-faint ring-1 ring-navy-700 focus:outline-none focus:ring-sun"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="rounded-xl bg-sun px-3.5 py-1.5 text-sm font-bold text-navy-900 hover:bg-sun-deep disabled:opacity-40"
          >
            Post
          </button>
        </form>
        <div className="flex justify-between text-xs">
          <span className="text-danger" role="alert">
            {formError}
          </span>
          <span className="text-faint" aria-live="polite">
            {draft.length}/{MAX_COMMENT}
          </span>
        </div>
      </div>
    </div>
  );
}
