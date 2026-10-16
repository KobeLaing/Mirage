"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, api, setCsrfToken, setUnauthorizedHandler } from "./api";
import type { Profile, RankKey } from "./types";

type Status = "loading" | "signedIn" | "signedOut" | "error";

interface AuthState {
  status: Status;
  me: Profile | null;
  userId: number | null;
  /** Saved on the server; when on, the API withholds counts/comments until you vote. */
  blindMode: boolean;
  setBlindMode: (enabled: boolean) => Promise<void>;
  login: (username: string, password: string, website: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
  /** Apply the XP/rank the server returned after a vote, without refetching. */
  applyStanding: (standing: { xp: number; rank: RankKey }) => void;
  retry: () => void;
}

const Ctx = createContext<AuthState | null>(null);

export const LOGIN_PATH = "/login";

/**
 * Who is signed in, for the whole app.
 *
 * On first load it asks the API "am I signed in?" (GET /auth/session). The
 * browser sends the httpOnly session cookie automatically; we never read it.
 * The answer gives us the profile and the CSRF token for later writes.
 *
 * Pages are only rendered once we know the answer (see AppShell), so signed-out
 * visitors never see a flash of private content. The API enforces sign-in on
 * every request regardless; this is about a clean experience, not security.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [status, setStatus] = useState<Status>("loading");
  const [me, setMe] = useState<Profile | null>(null);
  const [blindMode, setBlindModeState] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const signedOut = useCallback(() => {
    setCsrfToken(null);
    setMe(null);
    setStatus("signedOut");
  }, []);

  // Any 401 from the API (session expired or revoked) lands here.
  useEffect(() => {
    setUnauthorizedHandler(signedOut);
    return () => setUnauthorizedHandler(null);
  }, [signedOut]);

  useEffect(() => {
    const controller = new AbortController();
    api
      .session(controller.signal)
      .then((session) => {
        setCsrfToken(session.csrf_token);
        setMe(session.user);
        setBlindModeState(session.blind_mode);
        setStatus("signedIn");
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        if (err instanceof ApiError && err.status === 401) signedOut();
        else setStatus("error");
      });
    return () => controller.abort();
  }, [attempt, signedOut]);

  // Keep the URL in step with the session: signed-out users go to /login,
  // signed-in users don't sit on the login page.
  useEffect(() => {
    if (status === "signedOut" && pathname !== LOGIN_PATH) router.replace(LOGIN_PATH);
    if (status === "signedIn" && pathname === LOGIN_PATH) router.replace("/");
  }, [status, pathname, router]);

  const login = useCallback(async (username: string, password: string, website: string) => {
    const session = await api.login(username, password, website);
    setCsrfToken(session.csrf_token);
    setMe(session.user);
    setBlindModeState(session.blind_mode);
    setStatus("signedIn");
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      signedOut();
    }
  }, [signedOut]);

  const refreshMe = useCallback(async () => {
    setMe(await api.me());
  }, []);

  const applyStanding = useCallback(
    (standing: { xp: number; rank: RankKey }) => {
      // Show the new XP immediately; rank details and progress are computed by the
      // server, so refresh them in the background.
      setMe((prev) => (prev ? { ...prev, xp: standing.xp } : prev));
      refreshMe().catch(() => undefined);
    },
    [refreshMe],
  );

  const setBlindMode = useCallback(async (enabled: boolean) => {
    const state = await api.setBlindMode(enabled);
    setBlindModeState(state.blind_mode);
  }, []);

  const retry = useCallback(() => {
    setStatus("loading");
    setAttempt((n) => n + 1);
  }, []);

  const value = useMemo(
    () => ({
      status, me, userId: me?.id ?? null, blindMode, setBlindMode, login, logout, refreshMe, applyStanding, retry,
    }),
    [status, me, blindMode, setBlindMode, login, logout, refreshMe, applyStanding, retry],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
