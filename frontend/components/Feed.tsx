"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Post } from "@/lib/types";
import { PostCard } from "./PostCard";
import { EmptyState, ErrorState, LoadingState, PostSkeleton } from "./states";

interface FeedState {
  key: string;
  posts: Post[];
  cursor: string | null;
  error: unknown;
}

/** Community posts, newest first, loaded a page at a time with a cursor (FR-11, FR-12). */
export function Feed({ newPosts = [] }: { newPosts?: Post[] }) {
  const { userId, blindMode } = useAuth();
  const [reload, setReload] = useState(0);
  // Reload when Blind Mode flips: the server sends different data per post.
  const key = `${userId}:${blindMode}:${reload}`;
  const [state, setState] = useState<FeedState>({ key: "", posts: [], cursor: null, error: null });
  const [removed, setRemoved] = useState<Set<number>>(new Set());
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState<string | null>(null);
  const sentinel = useRef<HTMLDivElement>(null);

  // Load the first page (again when "Try again" bumps `reload`).
  useEffect(() => {
    const controller = new AbortController();
    api
      .feed(null, controller.signal)
      .then((page) => setState({ key, posts: page.items, cursor: page.next_cursor, error: null }))
      .catch((err) => {
        if (!controller.signal.aborted) setState({ key, posts: [], cursor: null, error: err });
      });
    return () => controller.abort();
  }, [key]);

  const loadMore = useCallback(async () => {
    if (!state.cursor || loadingMore) return;
    setLoadingMore(true);
    setMoreError(null);
    try {
      const page = await api.feed(state.cursor);
      setState((s) => ({ ...s, posts: [...s.posts, ...page.items], cursor: page.next_cursor }));
    } catch (err) {
      setMoreError(errorMessage(err));
    } finally {
      setLoadingMore(false);
    }
  }, [state.cursor, loadingMore]);

  // Infinite scroll: fetch the next page as the end of the list approaches.
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !state.cursor || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting) void loadMore();
    }, { rootMargin: "600px" });
    observer.observe(el);
    return () => observer.disconnect();
  }, [state.cursor, loadMore]);

  const onDeleted = useCallback((id: number) => setRemoved((prev) => new Set(prev).add(id)), []);

  if (state.key !== key) return <LoadingState label="Loading posts" />;
  if (state.error) return <ErrorState error={state.error} onRetry={() => setReload((n) => n + 1)} />;

  const seen = new Set<number>();
  const posts = [...newPosts, ...state.posts].filter((p) => {
    if (removed.has(p.id) || seen.has(p.id)) return false;
    seen.add(p.id);
    return true;
  });

  if (posts.length === 0) {
    return <EmptyState title="No posts yet" hint="Be the first to share something that looks a little too perfect." />;
  }

  return (
    <div className="space-y-4">
      {posts.map((post) => (
        <PostCard key={`${post.id}:${key}`} post={post} onDeleted={onDeleted} />
      ))}
      <div ref={sentinel} />
      {loadingMore && <PostSkeleton />}
      {moreError && <ErrorState error={new Error(moreError)} onRetry={loadMore} />}
      {state.cursor && !loadingMore && !moreError && (
        <button
          type="button"
          onClick={loadMore}
          className="w-full rounded-xl bg-navy-800 py-3 text-sm font-semibold text-muted ring-1 ring-navy-700 hover:text-ink"
        >
          Load more
        </button>
      )}
      {!state.cursor && <p className="py-4 text-center text-sm text-faint">You&apos;re all caught up.</p>}
    </div>
  );
}
