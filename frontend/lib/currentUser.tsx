"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, errorMessage } from "./api";
import type { Profile, RankKey, UserSummary } from "./types";

const STORAGE_KEY = "mirage.userId";

interface CurrentUserState {
  users: UserSummary[];
  userId: number | null;
  me: Profile | null;
  error: string | null;
  ready: boolean;
  switchTo: (id: number) => void;
  refreshMe: () => Promise<void>;
  /** Apply the XP/rank the server returned after a vote, without refetching. */
  applyStanding: (standing: { xp: number; rank: RankKey }) => void;
  retry: () => void;
}

const Ctx = createContext<CurrentUserState | null>(null);

function readStored(): number | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw && /^\d+$/.test(raw) ? Number(raw) : null;
  } catch {
    return null;
  }
}

function writeStored(id: number) {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(id));
  } catch {
    // Storage can be unavailable (private mode); the switcher still works for this tab.
  }
}

/**
 * DEV-ONLY identity: which seeded account the person at the keyboard is acting as.
 * The id is sent as X-User-Id; the backend resolves it in one dependency that
 * real authentication will replace.
 */
export function CurrentUserProvider({ children }: { children: React.ReactNode }) {
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [userId, setUserId] = useState<number | null>(null);
  const [me, setMe] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .users()
      .then((list) => {
        if (cancelled) return;
        const stored = readStored();
        const chosen = list.find((u) => u.id === stored)?.id ?? list[0]?.id ?? null;
        setUsers(list);
        setUserId(chosen);
        setError(null);
        setReady(true);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(errorMessage(err));
        setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  useEffect(() => {
    if (userId == null) return;
    let cancelled = false;
    api
      .me(userId)
      .then((profile) => !cancelled && setMe(profile))
      .catch(() => !cancelled && setMe(null));
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const switchTo = useCallback((id: number) => {
    writeStored(id);
    setMe(null);
    setUserId(id);
  }, []);

  const refreshMe = useCallback(async () => {
    if (userId == null) return;
    setMe(await api.me(userId));
  }, [userId]);

  const applyStanding = useCallback(
    (standing: { xp: number; rank: RankKey }) => {
      // Show the new XP immediately; rank details and progress are computed by the
      // server, so refresh them in the background.
      setMe((prev) => (prev ? { ...prev, xp: standing.xp } : prev));
      refreshMe().catch(() => undefined);
    },
    [refreshMe],
  );

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  const value = useMemo(
    () => ({ users, userId, me, error, ready, switchTo, refreshMe, applyStanding, retry }),
    [users, userId, me, error, ready, switchTo, refreshMe, applyStanding, retry],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCurrentUser(): CurrentUserState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCurrentUser must be used inside CurrentUserProvider");
  return ctx;
}
