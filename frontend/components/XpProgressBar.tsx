import type { Profile } from "@/lib/types";
import { RANK_STYLES } from "./RankBadge";

export function XpProgressBar({ profile }: { profile: Profile }) {
  const { xp, rank, next_rank: next, progress } = profile;
  const pct = Math.round(progress * 100);
  const current = RANK_STYLES[rank.key];
  const label = next
    ? `${xp - rank.min_xp} of ${next.min_xp - rank.min_xp} XP toward ${next.name}`
    : "Maximum rank reached";

  return (
    <div className="w-full">
      <div className="mb-1.5 flex items-baseline justify-between text-xs">
        <span className="font-semibold text-ink">{xp} XP</span>
        <span className="text-muted">{next ? `Next: ${next.name} at ${next.min_xp} XP` : "Top rank"}</span>
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-3 w-full overflow-hidden rounded-full bg-navy-950 ring-1 ring-navy-700"
      >
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${current.base}, ${next ? RANK_STYLES[next.key].base : current.shine})`,
          }}
        />
      </div>
      <p className="mt-1 text-xs text-faint">{label}</p>
    </div>
  );
}
