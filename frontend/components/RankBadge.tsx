import { useId } from "react";

import type { RankKey } from "@/lib/types";

// Five medal colours chosen to differ in both hue and lightness, so they stay
// distinguishable for common colour-vision deficiencies. Each also carries its
// rank number (1-5) as a non-colour cue (FR-57).
export const RANK_STYLES: Record<RankKey, { name: string; base: string; shine: string; rim: string; tier: number }> = {
  bronze: { name: "Bronze Verifier", base: "#A0522D", shine: "#DDA071", rim: "#5E2E0E", tier: 1 },
  silver: { name: "Silver Verifier", base: "#B8C2CC", shine: "#F4F7FA", rim: "#6E7B88", tier: 2 },
  gold: { name: "Gold Verifier", base: "#E8B004", shine: "#FFE680", rim: "#9A6A00", tier: 3 },
  platinum: { name: "Platinum Verifier", base: "#7FD3D8", shine: "#E3FCFD", rim: "#2F8A90", tier: 4 },
  palladium: { name: "Palladium Verifier", base: "#6B5BD6", shine: "#CBC3FF", rim: "#33288A", tier: 5 },
};

const RIBBON_BLUE = "#1E4FD8";
const RIBBON_RED = "#D62839";

interface RankBadgeProps {
  rank: RankKey;
  size?: number; // height in px; width is 3/4 of it
  className?: string;
}

/** A medal in the rank's colour hanging from a blue-red-blue striped ribbon. */
export function RankBadge({ rank, size = 48, className }: RankBadgeProps) {
  const uid = useId();
  const style = RANK_STYLES[rank] ?? RANK_STYLES.bronze;
  const face = `${uid}-face`;
  const ribbonClip = `${uid}-ribbon`;

  return (
    <svg
      viewBox="0 0 48 64"
      width={(size * 3) / 4}
      height={size}
      className={className}
      role="img"
      aria-label={`${style.name} badge`}
    >
      <defs>
        <radialGradient id={face} cx="38%" cy="32%" r="75%">
          <stop offset="0%" stopColor={style.shine} />
          <stop offset="55%" stopColor={style.base} />
          <stop offset="100%" stopColor={style.rim} />
        </radialGradient>
        <clipPath id={ribbonClip}>
          <path d="M11 0 H37 L33 32 H15 Z" />
        </clipPath>
      </defs>

      {/* Ribbon: three vertical stripes, blue / red / blue */}
      <g clipPath={`url(#${ribbonClip})`}>
        <rect x="11" y="0" width="9.5" height="32" fill={RIBBON_BLUE} />
        <rect x="20.5" y="0" width="7" height="32" fill={RIBBON_RED} />
        <rect x="27.5" y="0" width="9.5" height="32" fill={RIBBON_BLUE} />
        <rect x="11" y="0" width="26" height="3" fill="#000" opacity="0.18" />
      </g>
      <path d="M11 0 H37 L33 32 H15 Z" fill="none" stroke="#071226" strokeOpacity="0.5" strokeWidth="1" />

      {/* Clasp */}
      <rect x="18.5" y="28" width="11" height="6" rx="2" fill={style.rim} />
      <rect x="20" y="29.3" width="8" height="1.6" rx="0.8" fill={style.shine} opacity="0.7" />

      {/* Medal */}
      <circle cx="24" cy="47" r="16" fill={style.rim} />
      <circle cx="24" cy="47" r="13.2" fill={`url(#${face})`} />
      <circle cx="24" cy="47" r="10.6" fill="none" stroke={style.rim} strokeOpacity="0.55" strokeWidth="1" />
      <text
        x="24"
        y="52"
        textAnchor="middle"
        fontSize="13"
        fontWeight="800"
        fontFamily="ui-sans-serif, system-ui, sans-serif"
        fill={style.rim}
      >
        {style.tier}
      </text>
      <path d="M14.5 41 A11 11 0 0 1 21 36.5" stroke="#fff" strokeOpacity="0.55" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  );
}
