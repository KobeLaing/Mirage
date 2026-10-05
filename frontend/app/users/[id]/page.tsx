"use client";

import { use, useEffect, useState } from "react";

import { ActivityList } from "@/components/ActivityList";
import { PostComposer } from "@/components/PostComposer";
import { ProfileHeader } from "@/components/ProfileHeader";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { api } from "@/lib/api";
import { useCurrentUser } from "@/lib/currentUser";
import type { Activity, Profile } from "@/lib/types";

interface Loaded {
  key: string;
  profile: Profile | null;
  activity: Activity | null;
  error: unknown;
}

export default function ProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const profileId = /^\d{1,12}$/.test(id) ? Number(id) : null;
  const { userId, ready, me } = useCurrentUser();
  const [reload, setReload] = useState(0);
  const key = `${profileId}:${userId}:${reload}`;
  const [data, setData] = useState<Loaded>({ key: "", profile: null, activity: null, error: null });

  useEffect(() => {
    if (!ready || profileId == null) return;
    const controller = new AbortController();
    Promise.all([api.profile(profileId, controller.signal), api.activity(profileId, userId, controller.signal)])
      .then(([profile, activity]) => setData({ key, profile, activity, error: null }))
      .catch((error) => {
        if (!controller.signal.aborted) setData({ key, profile: null, activity: null, error });
      });
    return () => controller.abort();
  }, [ready, profileId, userId, key]);

  if (profileId == null) return <EmptyState title="Profile not found" />;
  if (!ready || data.key !== key) return <LoadingState label="Loading profile" count={1} />;
  if (data.error || !data.profile || !data.activity) {
    return <ErrorState error={data.error} onRetry={() => setReload((n) => n + 1)} />;
  }

  const isMe = userId === profileId;
  // On your own profile, show live XP from the header's state (updated after every vote).
  const profile = isMe && me?.id === profileId ? me : data.profile;

  return (
    <div className="space-y-6">
      <ProfileHeader profile={profile} isMe={isMe} onAvatarChanged={() => setReload((n) => n + 1)} />
      {isMe && <PostComposer onCreated={() => setReload((n) => n + 1)} />}
      <section aria-labelledby="activity-heading" className="space-y-4">
        <h2 id="activity-heading" className="text-lg font-bold text-ink">
          Recent activity
        </h2>
        <ActivityList items={data.activity.items} viewerKey={`${userId}:${reload}`} />
      </section>
    </div>
  );
}
