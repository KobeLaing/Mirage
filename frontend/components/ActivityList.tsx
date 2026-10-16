"use client";

import { useCallback, useState } from "react";

import type { ActivityItem } from "@/lib/types";
import { CheckCircleIcon, RobotIcon, UploadIcon } from "./icons";
import { PostCard } from "./PostCard";
import { EmptyState } from "./states";

function ActivityLabel({ item }: { item: ActivityItem }) {
  if (item.type === "posted") {
    return (
      <span className="flex items-center gap-1 rounded-full bg-sun/15 px-2.5 py-1 text-xs font-bold text-sun">
        <UploadIcon className="h-3.5 w-3.5" /> Posted
      </span>
    );
  }
  if (item.vote === null) {
    // Blind Mode withholds how this person voted until you vote yourself.
    return <span className="rounded-full bg-navy-700 px-2.5 py-1 text-xs font-bold text-muted">Voted</span>;
  }
  const isAI = item.vote === "AI";
  return (
    <span
      className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${
        isAI ? "bg-ai/15 text-ai" : "bg-real/15 text-real"
      }`}
    >
      {isAI ? <RobotIcon className="h-3.5 w-3.5" /> : <CheckCircleIcon className="h-3.5 w-3.5" />}
      Voted {isAI ? "AI" : "Real"}
    </span>
  );
}

export function ActivityList({ items, viewerKey }: { items: ActivityItem[]; viewerKey: string }) {
  const [removed, setRemoved] = useState<Set<number>>(new Set());
  const onDeleted = useCallback((id: number) => setRemoved((prev) => new Set(prev).add(id)), []);
  const visible = items.filter((i) => !removed.has(i.post.id));

  if (visible.length === 0) {
    return <EmptyState title="No activity yet" hint="Votes and posts will show up here." />;
  }
  return (
    <ol className="space-y-4">
      {visible.map((item) => (
        <li key={`${item.type}:${item.post.id}:${viewerKey}`}>
          <PostCard post={item.post} onDeleted={onDeleted} label={<ActivityLabel item={item} />} />
        </li>
      ))}
    </ol>
  );
}
