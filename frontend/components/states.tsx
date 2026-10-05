import { ApiError } from "@/lib/api";

export function PostSkeleton() {
  return (
    <div className="rounded-2xl bg-navy-800 p-3.5 ring-1 ring-navy-700" aria-hidden="true">
      <div className="flex items-center gap-3">
        <div className="skeleton h-10 w-10 rounded-full" />
        <div className="flex-1 space-y-2">
          <div className="skeleton h-3 w-32 rounded" />
          <div className="skeleton h-3 w-20 rounded" />
        </div>
      </div>
      <div className="skeleton mt-3 aspect-[16/10] w-full rounded-xl" />
      <div className="mt-4 flex gap-3">
        <div className="skeleton h-11 w-28 rounded-xl" />
        <div className="skeleton h-11 w-28 rounded-xl" />
      </div>
    </div>
  );
}

export function LoadingState({ label, count = 2 }: { label: string; count?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-4">
      <span className="sr-only">{label}</span>
      {Array.from({ length: count }, (_, i) => (
        <PostSkeleton key={i} />
      ))}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-navy-600 px-6 py-12 text-center">
      {/* eslint-disable-next-line @next/next/no-img-element -- static local SVG */}
      <img src="/logo.svg" alt="" width={56} height={56} className="mx-auto opacity-80" />
      <p className="mt-4 text-lg font-semibold text-ink">{title}</p>
      {hint && <p className="mt-1 text-sm text-muted">{hint}</p>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof ApiError ? error.message : "Something went wrong.";
  const requestId = error instanceof ApiError ? error.requestId : null;
  return (
    <div role="alert" className="rounded-2xl border border-danger/40 bg-danger/10 px-6 py-8 text-center">
      <p className="font-semibold text-ink">{message}</p>
      {requestId && <p className="mt-1 font-mono text-xs text-muted">Reference: {requestId}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded-lg bg-navy-700 px-4 py-2 text-sm font-semibold text-ink hover:bg-navy-600"
        >
          Try again
        </button>
      )}
    </div>
  );
}
