import type {
  Activity,
  FeedPage,
  Post,
  Profile,
  ReactionKind,
  ReactionState,
  UserSummary,
  VoteState,
  VoteValue,
} from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** An error in the backend's standard shape: {"error": {code, message, request_id}}. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId: string | null = null,
    public retryAfter: number | null = null,
  ) {
    super(message);
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  userId?: number | null;
  json?: unknown;
  form?: FormData;
  signal?: AbortSignal;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  // DEV identity: the account switcher's choice. Real auth replaces this header.
  if (opts.userId != null) headers["X-User-Id"] = String(opts.userId);
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form; // the browser sets the multipart boundary
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: opts.method ?? "GET", headers, body, signal: opts.signal });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "network_error", "Can't reach the Mirage server. Is the backend running?");
  }

  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const e = data?.error;
    const retry = res.headers.get("Retry-After");
    throw new ApiError(
      res.status,
      e?.code ?? "error",
      e?.message ?? `Request failed (${res.status}).`,
      e?.request_id ?? res.headers.get("X-Request-ID"),
      retry ? Number(retry) : null,
    );
  }
  return data as T;
}

export const api = {
  users: () => request<UserSummary[]>("/api/v1/users"),
  me: (userId: number) => request<Profile>("/api/v1/me", { userId }),
  profile: (id: number, signal?: AbortSignal) => request<Profile>(`/api/v1/users/${id}`, { signal }),
  activity: (id: number, viewerId: number | null, signal?: AbortSignal) =>
    request<Activity>(`/api/v1/users/${id}/activity`, { userId: viewerId, signal }),
  setAvatar: (userId: number, avatarId: number) =>
    request<Profile>("/api/v1/me/avatar", { method: "PUT", userId, json: { avatar_id: avatarId } }),

  feed: (viewerId: number | null, cursor: string | null, signal?: AbortSignal) => {
    const qs = new URLSearchParams({ limit: "10" });
    if (cursor) qs.set("cursor", cursor);
    return request<FeedPage>(`/api/v1/posts?${qs}`, { userId: viewerId, signal });
  },
  createPost: (userId: number, file: File, caption: string) => {
    const form = new FormData();
    form.append("file", file);
    if (caption.trim()) form.append("caption", caption);
    return request<Post>("/api/v1/posts", { method: "POST", userId, form });
  },
  deletePost: (userId: number, postId: number) =>
    request<void>(`/api/v1/posts/${postId}`, { method: "DELETE", userId }),

  vote: (userId: number, postId: number, value: VoteValue) =>
    request<VoteState>(`/api/v1/posts/${postId}/vote`, { method: "PUT", userId, json: { value } }),
  unvote: (userId: number, postId: number) =>
    request<VoteState>(`/api/v1/posts/${postId}/vote`, { method: "DELETE", userId }),
  react: (userId: number, postId: number, kind: ReactionKind) =>
    request<ReactionState>(`/api/v1/posts/${postId}/reaction`, { method: "PUT", userId, json: { kind } }),
  unreact: (userId: number, postId: number) =>
    request<ReactionState>(`/api/v1/posts/${postId}/reaction`, { method: "DELETE", userId }),
};

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "Something went wrong.";
}
