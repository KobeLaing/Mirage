"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { LeaderboardEntry } from "@/lib/types";
import { TrophyIcon } from "./icons";
import { RankBadge } from "./RankBadge";

/** Top 50 users by XP. The signed-in user's row is highlighted. */
export function Leaderboard() {
  const { me } = useAuth();
  const [items, setItems] = useState<LeaderboardEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Re-fetch whenever my XP changes, so my position updates after I vote or post.
  const myXp = me?.xp;
  useEffect(() => {
    const controller = new AbortController();
    api
      .leaderboard(controller.signal)
      .then((board) => {
        setItems(board.items);
        setError(null);
      })
      .catch((err) => !controller.signal.aborted && setError(errorMessage(err)));
    return () => controller.abort();
  }, [myXp]);

  return (
    <section aria-labelledby="leaderboard-heading" className="rounded-2xl bg-navy-800 p-3.5 ring-1 ring-navy-700">
      <h2 id="leaderboard-heading" className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-sun">
        <TrophyIcon className="h-4 w-4" /> Leaderboard
      </h2>
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
      {!items && !error && <div className="skeleton mt-3 h-40 rounded-xl" aria-hidden="true" />}
      {items && (
        <div className="mt-2 max-h-80 overflow-y-auto pr-1">
          <table className="w-full border-separate border-spacing-y-1 text-sm">
            <thead className="sr-only">
              <tr>
                <th scope="col">Position</th>
                <th scope="col">Name</th>
                <th scope="col">Verifier status</th>
                <th scope="col">Badge</th>
              </tr>
            </thead>
            <tbody>
              {items.map((entry) => {
                const isMe = entry.user.id === me?.id;
                return (
                  <tr key={entry.user.id} className={isMe ? "bg-sun/15" : ""}>
                    <td className="w-9 rounded-l-lg py-1.5 pl-2 font-bold tabular-nums text-muted">#{entry.position}</td>
                    <td className="max-w-0 py-1.5">
                      <Link
                        href={`/users/${entry.user.id}`}
                        className={`block truncate font-semibold hover:underline ${isMe ? "text-sun" : "text-ink"}`}
                      >
                        {entry.user.display_name}
                        {isMe && <span className="sr-only"> (you)</span>}
                      </Link>
                      <span className="block text-[11px] tabular-nums text-faint">{entry.xp} XP</span>
                    </td>
                    <td className="whitespace-nowrap py-1.5 pl-2 text-xs text-muted">{entry.rank_name}</td>
                    <td className="w-8 rounded-r-lg py-1.5 pr-2 text-right">
                      <RankBadge rank={entry.user.rank} size={22} className="inline-block" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
