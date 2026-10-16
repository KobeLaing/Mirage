"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/lib/auth";
import { Avatar } from "./Avatar";
import { RankBadge } from "./RankBadge";

/** The signed-in user's chip in the header: avatar, badge, XP and a sign-out button. */
export function UserMenu() {
  const { me, logout } = useAuth();
  const [busy, setBusy] = useState(false);
  if (!me) return null;

  return (
    <div className="flex items-center gap-2 rounded-full bg-navy-900/90 py-1 pl-1 pr-1.5 text-ink shadow-sm ring-1 ring-navy-950/40">
      <Link href={`/users/${me.id}`} className="flex items-center gap-2 rounded-full" aria-label="My profile">
        <Avatar avatarId={me.avatar_id} size={34} label="" />
        <RankBadge rank={me.rank.key} size={30} />
        <span className="flex flex-col leading-tight">
          <span className="max-w-[9rem] truncate text-sm font-semibold">{me.display_name}</span>
          <span className="text-[11px] font-semibold text-muted">{me.xp} XP</span>
        </span>
      </Link>
      <button
        type="button"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          await logout();
        }}
        className="ml-1 rounded-full px-3 py-1.5 text-xs font-bold text-sun ring-1 ring-sun/40 hover:bg-sun hover:text-navy-900 disabled:opacity-50"
      >
        Sign out
      </button>
    </div>
  );
}
