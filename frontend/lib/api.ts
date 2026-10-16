import type {
  Activity,
  Comment,
  CommentList,
  FeedPage,
  Leaderboard,
  Post,
  Profile,
  ReactionKind,
  ReactionState,
  ScanResult,
  SessionInfo,
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

/*
 * How requests are authenticated:
 * - The session lives in an httpOnly cookie that the API sets at login. This
 *   code never sees it; `credentials: "include"` just tells the browser to send it.
 * - Writes also need the CSRF token the API returned at login. It is kept only
 *   in memory (not localStorage), so it disappears with the tab and another
 *   site can't read it.
 * - Any 401 means the session ended (expired, revoked, logged out elsewhere),
 *   so we tell the auth provider, which sends the user back to /login.
 */
let csrfToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  json?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  /** Login/session checks handle their own 401s instead of triggering a redirect. */
  quiet401?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = {};
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form; // the browser sets the multipart boundary
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body, signal: opts.signal, credentials: "include" });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "network_error", "Can't reach the Mirage server. Is the backend running?");
  }

  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && !opts.quiet401) onUnauthorized?.();
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
  // "website" is the login form's honeypot field; real users always send "".
  login: (username: string, password: string, website: string) =>
    request<SessionInfo>("/api/v1/auth/login", {
      method: "POST",
      json: { username, password, website },
      quiet401: true,
    }),
  logout: () => request<void>("/api/v1/auth/logout", { method: "POST", quiet401: true }),
  session: (signal?: AbortSignal) => request<SessionInfo>("/api/v1/auth/session", { signal, quiet401: true }),

  me: () => request<Profile>("/api/v1/me"),
  profile: (id: number, signal?: AbortSignal) => request<Profile>(`/api/v1/users/${id}`, { signal }),
  activity: (id: number, signal?: AbortSignal) => request<Activity>(`/api/v1/users/${id}/activity`, { signal }),
  setBlindMode: (enabled: boolean) =>
    request<{ blind_mode: boolean }>("/api/v1/me/blind-mode", { method: "PUT", json: { enabled } }),
  setAvatar: (avatarId: number) => request<Profile>("/api/v1/me/avatar", { method: "PUT", json: { avatar_id: avatarId } }),

  feed: (cursor: string | null, signal?: AbortSignal) => {
    const qs = new URLSearchParams({ limit: "10" });
    if (cursor) qs.set("cursor", cursor);
    return request<FeedPage>(`/api/v1/posts?${qs}`, { signal });
  },
  createPost: (file: File, caption: string) => {
    const form = new FormData();
    form.append("file", file);
    if (caption.trim()) form.append("caption", caption);
    return request<Post>("/api/v1/posts", { method: "POST", form });
  },
  post: (postId: number) => request<Post>(`/api/v1/posts/${postId}`),
  deletePost: (postId: number) => request<void>(`/api/v1/posts/${postId}`, { method: "DELETE" }),

  vote: (postId: number, value: VoteValue) =>
    request<VoteState>(`/api/v1/posts/${postId}/vote`, { method: "PUT", json: { value } }),
  unvote: (postId: number) => request<VoteState>(`/api/v1/posts/${postId}/vote`, { method: "DELETE" }),
  react: (postId: number, kind: ReactionKind) =>
    request<ReactionState>(`/api/v1/posts/${postId}/reaction`, { method: "PUT", json: { kind } }),
  unreact: (postId: number) => request<ReactionState>(`/api/v1/posts/${postId}/reaction`, { method: "DELETE" }),

  scan: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ScanResult>("/api/v1/scanner", { method: "POST", form });
  },

  leaderboard: (signal?: AbortSignal) => request<Leaderboard>("/api/v1/leaderboard", { signal }),

  comments: (postId: number, signal?: AbortSignal) =>
    request<CommentList>(`/api/v1/posts/${postId}/comments`, { signal }),
  addComment: (postId: number, body: string) =>
    request<Comment>(`/api/v1/posts/${postId}/comments`, { method: "POST", json: { body } }),
  deleteComment: (commentId: number) => request<void>(`/api/v1/comments/${commentId}`, { method: "DELETE" }),
};

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "Something went wrong.";
}
