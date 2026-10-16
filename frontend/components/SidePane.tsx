"use client";

import { BlindModeToggle } from "./BlindModeToggle";
import { Leaderboard } from "./Leaderboard";
import { Scanner } from "./Scanner";

/** The left-hand column on the feed and profile pages: leaderboard, Blind Mode, scanner. */
export function SidePane() {
  return (
    <div className="space-y-4">
      <Leaderboard />
      <BlindModeToggle />
      <Scanner />
    </div>
  );
}
