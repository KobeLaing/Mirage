"use client";

import { useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useCurrentUser } from "@/lib/currentUser";
import { Avatar, AVATAR_IDS, AVATAR_NAMES } from "./Avatar";

/** Shown inside the "change avatar" dialog on your own profile; the API only offers PUT /me/avatar anyway. */
export function AvatarPicker({ current, onChanged }: { current: number; onChanged: () => void }) {
  const { userId, refreshMe } = useCurrentUser();
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function pick(id: number) {
    if (userId == null || id === current || busy) return;
    setBusy(id);
    setError(null);
    try {
      await api.setAvatar(userId, id);
      await refreshMe();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <fieldset>
      <legend className="sr-only">Choose your avatar</legend>
      <div className="grid grid-cols-5 gap-3">
        {AVATAR_IDS.map((id) => {
          const selected = id === current;
          return (
            <button
              key={id}
              type="button"
              onClick={() => pick(id)}
              aria-pressed={selected}
              aria-label={`${AVATAR_NAMES[id - 1]} avatar${selected ? " (current)" : ""}`}
              disabled={busy != null}
              className={`rounded-full p-0.5 transition ${
                selected ? "ring-2 ring-sun" : "opacity-80 ring-1 ring-navy-600 hover:opacity-100 hover:ring-muted"
              } ${busy === id ? "animate-pulse" : ""}`}
            >
              <Avatar avatarId={id} size={56} label="" />
            </button>
          );
        })}
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </fieldset>
  );
}
