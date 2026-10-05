"use client";

import { useEffect, useRef } from "react";

import type { Media } from "@/lib/types";

/**
 * Lazy-loaded media (FR-13). Images use native lazy loading; videos are muted,
 * never autoplay, only fetch metadata up front, and pause when scrolled away.
 */
export function PostMedia({ media, alt }: { media: Media; alt: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const aspect = media.width && media.height ? `${media.width} / ${media.height}` : "16 / 9";

  useEffect(() => {
    const video = videoRef.current;
    if (!video || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting && !video.paused) video.pause();
      },
      { threshold: 0.2 },
    );
    observer.observe(video);
    return () => observer.disconnect();
  }, []);

  if (media.kind === "video") {
    return (
      <video
        ref={videoRef}
        src={media.url}
        controls
        muted
        playsInline
        preload="metadata"
        className="max-h-[min(52vh,460px)] w-full rounded-xl bg-navy-950"
        style={{ aspectRatio: aspect }}
        aria-label={alt}
      />
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- remote user media from our API; native lazy-loading is enough
    <img
      src={media.url}
      alt={alt}
      loading="lazy"
      decoding="async"
      width={media.width ?? undefined}
      height={media.height ?? undefined}
      className="max-h-[min(52vh,460px)] w-full rounded-xl bg-navy-950 object-contain"
      style={{ aspectRatio: aspect }}
    />
  );
}
