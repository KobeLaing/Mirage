"use client";

import { useCurrentUser } from "@/lib/currentUser";
import { Avatar } from "./Avatar";
import { RankBadge } from "./RankBadge";

/** DEV-ONLY: choose which seeded account to act as. Replaced by sign-in when real auth lands. */
export function AccountSwitcher() {
  const { users, userId, me, switchTo, ready, error } = useCurrentUser();
  const current = users.find((u) => u.id === userId);

  if (!ready) return <div className="h-10 w-48 rounded-full bg-navy-900/20" aria-hidden="true" />;
  if (error || !current) {
    return <span className="text-sm font-semibold text-navy-900">Offline</span>;
  }

  return (
    <div className="flex items-center gap-2 rounded-full bg-navy-900/90 py-1 pl-1 pr-3 text-ink shadow-sm ring-1 ring-navy-950/40">
      <Avatar avatarId={me?.avatar_id ?? current.avatar_id} size={34} />
      <RankBadge rank={me?.rank.key ?? current.rank} size={30} />
      <label className="flex flex-col leading-tight">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-sun">Acting as</span>
        <select
          value={userId ?? ""}
          onChange={(e) => switchTo(Number(e.target.value))}
          className="cursor-pointer bg-transparent text-sm font-semibold text-ink focus-visible:outline-none"
          aria-label="Switch account (development only)"
        >
          {users.map((u) => (
            <option key={u.id} value={u.id} className="bg-navy-900">
              {u.display_name}
            </option>
          ))}
        </select>
      </label>
      {me && <span className="ml-1 hidden text-xs font-semibold text-muted sm:inline">{me.xp} XP</span>}
    </div>
  );
}
