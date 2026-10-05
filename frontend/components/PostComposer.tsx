"use client";

import { useEffect, useId, useRef, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useCurrentUser } from "@/lib/currentUser";
import type { Post } from "@/lib/types";
import { CloseIcon, UploadIcon } from "./icons";

// Client-side checks are only for quick feedback. The server re-checks
// everything from the file's actual bytes (SR-1..3).
const ACCEPT = "image/jpeg,image/png,image/gif,video/mp4";
const MAX_IMAGE = 10 * 1024 * 1024;
const MAX_VIDEO = 50 * 1024 * 1024;
const MAX_CAPTION = 500;

function precheck(file: File): string | null {
  if (!ACCEPT.split(",").includes(file.type)) return "Choose a JPEG, PNG or GIF image, or an MP4 video.";
  const isVideo = file.type.startsWith("video/");
  if (file.size > (isVideo ? MAX_VIDEO : MAX_IMAGE)) return `That file is over ${isVideo ? 50 : 10} MB.`;
  return null;
}

export function PostComposer({ onCreated }: { onCreated?: (post: Post) => void }) {
  const { userId, refreshMe } = useCurrentUser();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [caption, setCaption] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const captionId = useId();

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  function choose(next: File | null) {
    setError(null);
    if (!next) return;
    const problem = precheck(next);
    if (problem) {
      setError(problem);
      return;
    }
    setFile(next);
    setPreview(URL.createObjectURL(next));
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setCaption("");
    if (inputRef.current) inputRef.current.value = "";
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || userId == null || busy) return;
    setBusy(true);
    setError(null);
    try {
      const post = await api.createPost(userId, file, caption);
      reset();
      onCreated?.(post);
      refreshMe().catch(() => undefined); // +25 XP
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const isVideo = file?.type.startsWith("video/");

  return (
    <form onSubmit={submit} className="rounded-2xl bg-navy-800 p-3.5 ring-1 ring-navy-700" aria-label="Create a post">
      <h2 className="text-sm font-bold uppercase tracking-wider text-sun">Spotted something suspicious?</h2>

      {!file ? (
        <label
          htmlFor={inputId}
          className="mt-2.5 flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-dashed border-navy-600 px-4 py-5 text-center text-muted transition-colors hover:border-sun hover:text-ink focus-within:border-sun"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            choose(e.dataTransfer.files?.[0] ?? null);
          }}
        >
          <UploadIcon className="h-6 w-6" />
          <span className="font-semibold">Upload one image or video</span>
          <span className="text-xs">JPEG, PNG, GIF up to 10 MB · MP4 up to 50 MB</span>
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept={ACCEPT}
            className="sr-only"
            onChange={(e) => choose(e.target.files?.[0] ?? null)}
          />
        </label>
      ) : (
        <div className="relative mt-2.5">
          {isVideo ? (
            <video src={preview ?? undefined} controls muted playsInline className="max-h-60 w-full rounded-xl bg-navy-950" />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element -- local blob preview
            <img src={preview ?? undefined} alt="Selected upload preview" className="max-h-60 w-full rounded-xl bg-navy-950 object-contain" />
          )}
          <button
            type="button"
            onClick={reset}
            className="absolute right-2 top-2 rounded-full bg-navy-950/80 p-1.5 text-ink hover:bg-navy-950"
            aria-label="Remove selected file"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        </div>
      )}

      <label htmlFor={captionId} className="sr-only">
        Caption (optional)
      </label>
      <textarea
        id={captionId}
        value={caption}
        onChange={(e) => setCaption(e.target.value)}
        maxLength={MAX_CAPTION}
        rows={2}
        placeholder="Add a caption (optional)"
        className="mt-2.5 w-full resize-none rounded-xl bg-navy-900 px-3 py-1.5 text-sm text-ink placeholder:text-faint ring-1 ring-navy-700 focus:outline-none focus:ring-sun"
      />

      <div className="mt-2 flex items-center gap-3">
        <span className="text-xs text-faint" aria-live="polite">
          {caption.length}/{MAX_CAPTION}
        </span>
        {error && (
          <span role="alert" className="text-sm text-danger">
            {error}
          </span>
        )}
        <button
          type="submit"
          disabled={!file || busy || userId == null}
          className="ml-auto rounded-xl bg-sun px-5 py-1.5 text-sm font-bold text-navy-900 shadow transition hover:bg-sun-deep disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Posting…" : "Post"}
        </button>
      </div>
    </form>
  );
}
