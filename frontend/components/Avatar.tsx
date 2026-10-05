import { useId } from "react";

// Ten original cartoon avatars (FR-4), each drawn on a 64x64 grid inside a circle.

export const AVATAR_NAMES = [
  "Cat", "Owl", "Astronaut", "Frog", "Bear", "Octopus", "Ghost", "Panda", "Alien", "Penguin",
] as const;

export const AVATAR_IDS = AVATAR_NAMES.map((_, i) => i + 1);

const BACKGROUNDS = [
  "#FDBA74", "#A7F3D0", "#1E3A8A", "#FDE68A", "#C4B5FD",
  "#99F6E4", "#4338CA", "#BBF7D0", "#F0ABFC", "#BAE6FD",
];

function Face({ id }: { id: number }) {
  switch (id) {
    case 1: // Cat
      return (
        <>
          <path d="M13 30 L18 9 L29 21 Z" fill="#EA7317" />
          <path d="M51 30 L46 9 L35 21 Z" fill="#EA7317" />
          <path d="M17 24 L19 15 L24 21 Z" fill="#FBCFE8" />
          <path d="M47 24 L45 15 L40 21 Z" fill="#FBCFE8" />
          <circle cx="32" cy="37" r="20" fill="#F97316" />
          <path d="M27 18 L29 25 M32 17 V25 M37 18 L35 25" stroke="#C2410C" strokeWidth="2" strokeLinecap="round" />
          <ellipse cx="32" cy="44" rx="10" ry="7" fill="#FFEDD5" />
          <ellipse cx="24.5" cy="34" rx="2.6" ry="3.8" fill="#1F2937" />
          <ellipse cx="39.5" cy="34" rx="2.6" ry="3.8" fill="#1F2937" />
          <circle cx="25.3" cy="32.6" r="0.9" fill="#fff" />
          <circle cx="40.3" cy="32.6" r="0.9" fill="#fff" />
          <path d="M29.5 40 H34.5 L32 42.8 Z" fill="#BE185D" />
          <path d="M32 42.8 V45 M32 45 Q29.5 47.5 27.5 45.5 M32 45 Q34.5 47.5 36.5 45.5" stroke="#7C2D12" strokeWidth="1.4" fill="none" strokeLinecap="round" />
          <path d="M8 40 L20 42 M8 46 L20 44.5 M56 40 L44 42 M56 46 L44 44.5" stroke="#7C2D12" strokeWidth="1.2" strokeLinecap="round" />
        </>
      );
    case 2: // Owl
      return (
        <>
          <path d="M14 22 L18 10 L26 18 Z M50 22 L46 10 L38 18 Z" fill="#78350F" />
          <ellipse cx="32" cy="40" rx="21" ry="24" fill="#92400E" />
          <ellipse cx="32" cy="50" rx="12" ry="12" fill="#D6A15B" />
          <path d="M26 46 q2 2 4 0 M34 46 q2 2 4 0 M30 52 q2 2 4 0" stroke="#92400E" strokeWidth="1.3" fill="none" />
          <circle cx="23.5" cy="32" r="9" fill="#FEF3C7" />
          <circle cx="40.5" cy="32" r="9" fill="#FEF3C7" />
          <circle cx="23.5" cy="32" r="4.6" fill="#111827" />
          <circle cx="40.5" cy="32" r="4.6" fill="#111827" />
          <circle cx="25" cy="30.5" r="1.4" fill="#fff" />
          <circle cx="42" cy="30.5" r="1.4" fill="#fff" />
          <path d="M29.5 38 H34.5 L32 43.5 Z" fill="#F59E0B" />
        </>
      );
    case 3: // Astronaut
      return (
        <>
          <circle cx="12" cy="12" r="1.2" fill="#FDE68A" />
          <circle cx="52" cy="16" r="1" fill="#FDE68A" />
          <circle cx="50" cy="52" r="1.2" fill="#FDE68A" />
          <rect x="18" y="50" width="28" height="16" rx="8" fill="#CBD5E1" />
          <circle cx="32" cy="33" r="21" fill="#E5E7EB" />
          <circle cx="32" cy="33" r="21" fill="none" stroke="#94A3B8" strokeWidth="2" />
          <rect x="17" y="22" width="30" height="22" rx="11" fill="#0EA5E9" />
          <path d="M22 28 Q26 24 31 25" stroke="#E0F2FE" strokeWidth="2.4" fill="none" strokeLinecap="round" />
          <circle cx="27" cy="34" r="2" fill="#0C4A6E" />
          <circle cx="37" cy="34" r="2" fill="#0C4A6E" />
          <path d="M29 39 Q32 41 35 39" stroke="#0C4A6E" strokeWidth="1.6" fill="none" strokeLinecap="round" />
          <rect x="9" y="29" width="4" height="9" rx="2" fill="#F97316" />
          <rect x="51" y="29" width="4" height="9" rx="2" fill="#F97316" />
        </>
      );
    case 4: // Frog
      return (
        <>
          <ellipse cx="32" cy="42" rx="23" ry="17" fill="#22C55E" />
          <circle cx="21" cy="26" r="9" fill="#22C55E" />
          <circle cx="43" cy="26" r="9" fill="#22C55E" />
          <circle cx="21" cy="26" r="5.5" fill="#fff" />
          <circle cx="43" cy="26" r="5.5" fill="#fff" />
          <circle cx="22" cy="27" r="2.8" fill="#14532D" />
          <circle cx="42" cy="27" r="2.8" fill="#14532D" />
          <path d="M18 44 Q32 54 46 44" stroke="#14532D" strokeWidth="2.2" fill="none" strokeLinecap="round" />
          <circle cx="15" cy="42" r="3" fill="#F9A8D4" opacity="0.8" />
          <circle cx="49" cy="42" r="3" fill="#F9A8D4" opacity="0.8" />
          <circle cx="29" cy="38" r="0.9" fill="#14532D" />
          <circle cx="35" cy="38" r="0.9" fill="#14532D" />
        </>
      );
    case 5: // Bear
      return (
        <>
          <circle cx="15" cy="19" r="8.5" fill="#92400E" />
          <circle cx="49" cy="19" r="8.5" fill="#92400E" />
          <circle cx="15" cy="19" r="4.5" fill="#F59E0B" />
          <circle cx="49" cy="19" r="4.5" fill="#F59E0B" />
          <circle cx="32" cy="36" r="21" fill="#B45309" />
          <ellipse cx="32" cy="44" rx="11" ry="8.5" fill="#FDE68A" />
          <ellipse cx="32" cy="40.5" rx="4.2" ry="3" fill="#3F1D0B" />
          <path d="M32 43.5 V46 M28.5 47 Q32 50 35.5 47" stroke="#3F1D0B" strokeWidth="1.6" fill="none" strokeLinecap="round" />
          <circle cx="24" cy="32" r="2.5" fill="#1C1917" />
          <circle cx="40" cy="32" r="2.5" fill="#1C1917" />
          <circle cx="24.8" cy="31.2" r="0.8" fill="#fff" />
          <circle cx="40.8" cy="31.2" r="0.8" fill="#fff" />
        </>
      );
    case 6: // Octopus
      return (
        <>
          <path d="M14 44 q-4 12 4 16 q2-8 6-8 q-1 10 6 12 q2-8 4-10 q2 8 7 9 q4-6 1-12 q6 3 9 8 q6-6-1-14 Z" fill="#DB2777" />
          <ellipse cx="32" cy="30" rx="19" ry="18" fill="#EC4899" />
          <ellipse cx="25" cy="31" rx="4.5" ry="5.5" fill="#fff" />
          <ellipse cx="39" cy="31" rx="4.5" ry="5.5" fill="#fff" />
          <circle cx="25.8" cy="32" r="2.6" fill="#1F2937" />
          <circle cx="39.8" cy="32" r="2.6" fill="#1F2937" />
          <path d="M28 40 Q32 43 36 40" stroke="#831843" strokeWidth="1.8" fill="none" strokeLinecap="round" />
          <circle cx="24" cy="19" r="2" fill="#F9A8D4" />
          <circle cx="37" cy="16" r="1.5" fill="#F9A8D4" />
          <circle cx="43" cy="22" r="2.2" fill="#F9A8D4" />
        </>
      );
    case 7: // Ghost
      return (
        <>
          <path d="M15 60 V30 a17 17 0 0 1 34 0 V60 l-5.7-4.5 -5.6 4.5 -5.7-4.5 -5.7 4.5 -5.6-4.5 Z" fill="#F8FAFC" />
          <ellipse cx="25.5" cy="30" rx="3.2" ry="4.6" fill="#1E1B4B" />
          <ellipse cx="38.5" cy="30" rx="3.2" ry="4.6" fill="#1E1B4B" />
          <circle cx="26.5" cy="28.4" r="1" fill="#fff" />
          <circle cx="39.5" cy="28.4" r="1" fill="#fff" />
          <ellipse cx="32" cy="40" rx="3" ry="3.6" fill="#1E1B4B" />
          <circle cx="20.5" cy="37" r="2.6" fill="#F9A8D4" opacity="0.8" />
          <circle cx="43.5" cy="37" r="2.6" fill="#F9A8D4" opacity="0.8" />
        </>
      );
    case 8: // Panda
      return (
        <>
          <circle cx="15" cy="18" r="8" fill="#111827" />
          <circle cx="49" cy="18" r="8" fill="#111827" />
          <circle cx="32" cy="36" r="21" fill="#F9FAFB" />
          <ellipse cx="23.5" cy="33" rx="5.5" ry="7" fill="#111827" transform="rotate(25 23.5 33)" />
          <ellipse cx="40.5" cy="33" rx="5.5" ry="7" fill="#111827" transform="rotate(-25 40.5 33)" />
          <circle cx="24.5" cy="32" r="2.2" fill="#fff" />
          <circle cx="39.5" cy="32" r="2.2" fill="#fff" />
          <circle cx="25" cy="32.5" r="1.1" fill="#111827" />
          <circle cx="39" cy="32.5" r="1.1" fill="#111827" />
          <ellipse cx="32" cy="42" rx="3.6" ry="2.6" fill="#111827" />
          <path d="M28.5 46.5 Q32 49.5 35.5 46.5" stroke="#111827" strokeWidth="1.6" fill="none" strokeLinecap="round" />
          <circle cx="18.5" cy="43" r="2.6" fill="#FBCFE8" />
          <circle cx="45.5" cy="43" r="2.6" fill="#FBCFE8" />
        </>
      );
    case 9: // Alien
      return (
        <>
          <path d="M23 15 L18 5 M41 15 L46 5" stroke="#65A30D" strokeWidth="2.2" strokeLinecap="round" />
          <circle cx="18" cy="5" r="3" fill="#FDE047" />
          <circle cx="46" cy="5" r="3" fill="#FDE047" />
          <path d="M32 12 C48 12 52 26 50 34 C48 46 40 56 32 56 C24 56 16 46 14 34 C12 26 16 12 32 12 Z" fill="#84CC16" />
          <ellipse cx="23.5" cy="33" rx="6" ry="8.5" fill="#1A2E05" transform="rotate(-28 23.5 33)" />
          <ellipse cx="40.5" cy="33" rx="6" ry="8.5" fill="#1A2E05" transform="rotate(28 40.5 33)" />
          <circle cx="21.5" cy="30" r="1.8" fill="#fff" />
          <circle cx="42.5" cy="30" r="1.8" fill="#fff" />
          <path d="M28.5 46 Q32 48.5 35.5 46" stroke="#1A2E05" strokeWidth="1.8" fill="none" strokeLinecap="round" />
        </>
      );
    default: // 10: Penguin
      return (
        <>
          <ellipse cx="32" cy="40" rx="20" ry="25" fill="#1F2937" />
          <ellipse cx="25.5" cy="34" rx="8.5" ry="9" fill="#F9FAFB" />
          <ellipse cx="38.5" cy="34" rx="8.5" ry="9" fill="#F9FAFB" />
          <ellipse cx="32" cy="47" rx="13.5" ry="13" fill="#F9FAFB" />
          <circle cx="26.5" cy="33" r="2.4" fill="#111827" />
          <circle cx="37.5" cy="33" r="2.4" fill="#111827" />
          <circle cx="27.2" cy="32.2" r="0.8" fill="#fff" />
          <circle cx="38.2" cy="32.2" r="0.8" fill="#fff" />
          <path d="M28 38 H36 L32 43 Z" fill="#F59E0B" />
          <circle cx="21" cy="41" r="2.5" fill="#FBCFE8" />
          <circle cx="43" cy="41" r="2.5" fill="#FBCFE8" />
        </>
      );
  }
}

interface AvatarProps {
  avatarId: number;
  size?: number;
  className?: string;
  label?: string;
}

export function Avatar({ avatarId, size = 40, className, label }: AvatarProps) {
  const clipId = useId();
  const id = AVATAR_IDS.includes(avatarId) ? avatarId : 1;
  const name = label ?? `${AVATAR_NAMES[id - 1]} avatar`;
  return (
    <svg
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={className}
      // label="" means decorative (the surrounding control already names it).
      role={name ? "img" : undefined}
      aria-label={name || undefined}
      aria-hidden={name ? undefined : true}
    >
      <defs>
        <clipPath id={clipId}>
          <circle cx="32" cy="32" r="32" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clipId})`}>
        <rect width="64" height="64" fill={BACKGROUNDS[id - 1]} />
        <Face id={id} />
      </g>
    </svg>
  );
}
