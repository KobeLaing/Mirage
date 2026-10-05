"use client";

import { useId, useRef } from "react";

import type { Profile } from "@/lib/types";
import { Avatar } from "./Avatar";
import { AvatarPicker } from "./AvatarPicker";
import { CloseIcon, PencilIcon } from "./icons";
import { RankBadge } from "./RankBadge";
import { XpProgressBar } from "./XpProgressBar";

interface ProfileHeaderProps {
  profile: Profile;
  isMe: boolean;
  onAvatarChanged: () => void;
}

/** Name, avatar, rank with badge, and XP progress toward the next rank (FR-40). */
export function ProfileHeader({ profile, isMe, onAvatarChanged }: ProfileHeaderProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  const avatar = <Avatar avatarId={profile.avatar_id} size={72} className="rounded-full ring-4 ring-navy-700" />;

  return (
    <section className="rounded-2xl bg-navy-800 p-4 ring-1 ring-navy-700" aria-labelledby="profile-name">
      <div className="flex items-center gap-4">
        {isMe ? (
          // Your own avatar is the entry point for changing it.
          <button
            type="button"
            onClick={() => dialogRef.current?.showModal()}
            aria-haspopup="dialog"
            aria-label="Change avatar"
            title="Change avatar"
            className="group relative shrink-0 rounded-full"
          >
            {avatar}
            <span className="absolute inset-0 rounded-full bg-navy-950/0 transition-colors group-hover:bg-navy-950/35" aria-hidden="true" />
            <span
              className="absolute bottom-0 right-0 flex h-6 w-6 items-center justify-center rounded-full bg-sun text-navy-900 shadow ring-2 ring-navy-800 transition-transform group-hover:scale-110"
              aria-hidden="true"
            >
              <PencilIcon className="h-3.5 w-3.5" />
            </span>
          </button>
        ) : (
          <div className="shrink-0">{avatar}</div>
        )}
        <div className="min-w-0 flex-1">
          <h1 id="profile-name" className="truncate text-2xl font-black text-ink">
            {profile.display_name}
          </h1>
          <p className="text-sm text-muted">@{profile.handle}</p>
          <p className="mt-1 text-sm font-bold text-sun">{profile.rank.name}</p>
        </div>
        <RankBadge rank={profile.rank.key} size={64} className="shrink-0 drop-shadow-lg" />
      </div>
      <div className="mt-4">
        <XpProgressBar profile={profile} />
      </div>

      {isMe && (
        // Native <dialog>: modal focus handling and Esc-to-close come from the browser.
        <dialog
          ref={dialogRef}
          aria-labelledby={titleId}
          onClick={(e) => {
            if (e.target === e.currentTarget) e.currentTarget.close(); // backdrop click
          }}
          className="fixed inset-0 m-auto h-fit w-[min(24rem,calc(100vw-2rem))] rounded-2xl bg-navy-800 p-0 text-ink shadow-2xl ring-1 ring-navy-600 backdrop:bg-navy-950/75 backdrop:backdrop-blur-sm"
        >
          <div className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 id={titleId} className="text-lg font-bold">
                Choose your avatar
              </h2>
              <button
                type="button"
                onClick={() => dialogRef.current?.close()}
                className="rounded-full p-1.5 text-muted hover:bg-navy-700 hover:text-ink"
                aria-label="Close"
              >
                <CloseIcon className="h-4 w-4" />
              </button>
            </div>
            <AvatarPicker
              current={profile.avatar_id}
              onChanged={() => {
                dialogRef.current?.close();
                onAvatarChanged();
              }}
            />
          </div>
        </dialog>
      )}
    </section>
  );
}
