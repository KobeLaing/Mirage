"use client";

import { useState } from "react";

import { Feed } from "@/components/Feed";
import { PostComposer } from "@/components/PostComposer";
import type { Post } from "@/lib/types";

export default function HomePage() {
  const [created, setCreated] = useState<Post[]>([]);
  return (
    <div className="space-y-5">
      <PostComposer onCreated={(post) => setCreated((prev) => [post, ...prev])} />
      <section aria-labelledby="feed-heading" className="space-y-4">
        <h1 id="feed-heading" className="text-lg font-bold text-ink">
          AI or real? <span className="font-normal text-muted">Cast your vote.</span>
        </h1>
        <Feed newPosts={created} />
      </section>
    </div>
  );
}
