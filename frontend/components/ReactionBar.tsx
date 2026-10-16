"use client";

import { useEffect, useId, useRef, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ReactionCounts, ReactionKind } from "@/lib/types";
import { HeartIcon, LaughIcon, LikeIcon, SmileOutlineIcon } from "./icons";

const KINDS: { kind: ReactionKind; label: string; Icon: typeof HeartIcon }[] = [
  { kind: "heart", label: "Heart", Icon: HeartIcon },
  { kind: "like", label: "Like", Icon: LikeIcon },
  { kind: "laugh", label: "Laugh", Icon: LaughIcon },
];

const LONG_PRESS_MS = 450;
const CLOSE_DELAY_MS = 180;

interface ReactionBarProps {
  postId: number;
  reactions: ReactionCounts;
  myReaction: ReactionKind | null;
}

/**
 * Secondary, deliberately quiet (FR-30..33): a small muted "React" control. The
 * tray of reactions appears on hover, on keyboard focus, or on a touch long-press.
 */
export function ReactionBar({ postId, reactions: initial, myReaction: initialMine }: ReactionBarProps) {
  const { userId } = useAuth();
  const [counts, setCounts] = useState(initial);
  const [mine, setMine] = useState(initialMine);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const longPressed = useRef(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const trayId = useId();

  useEffect(
    () => () => {
      if (closeTimer.current) clearTimeout(closeTimer.current);
      if (pressTimer.current) clearTimeout(pressTimer.current);
    },
    [],
  );

  const show = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    setOpen(true);
  };
  const hideSoon = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setOpen(false), CLOSE_DELAY_MS);
  };

  async function pick(kind: ReactionKind) {
    if (userId == null) return;
    const target = mine === kind ? null : kind;
    setError(null);
    try {
      const state = target ? await api.react(postId, target) : await api.unreact(postId);
      setCounts(state.reactions);
      setMine(state.my_reaction);
      setOpen(false);
      triggerRef.current?.focus();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const total = counts.heart + counts.like + counts.laugh;
  const Current = KINDS.find((k) => k.kind === mine)?.Icon ?? SmileOutlineIcon;

  return (
    <div
      className="relative"
      onMouseEnter={show}
      onMouseLeave={hideSoon}
      onFocus={show}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) hideSoon();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          setOpen(false);
          triggerRef.current?.focus();
        }
      }}
    >
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={trayId}
        aria-label={mine ? `Your reaction: ${mine}. Change reaction` : "React"}
        disabled={userId == null}
        className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-40 ${
          mine ? "text-muted" : "text-faint"
        } hover:bg-navy-700 hover:text-muted`}
        onClick={() => {
          // A long-press already opened the tray; don't let the release toggle it shut.
          if (longPressed.current) {
            longPressed.current = false;
            return;
          }
          setOpen((o) => !o);
        }}
        onPointerDown={(e) => {
          if (e.pointerType !== "touch") return;
          longPressed.current = false;
          pressTimer.current = setTimeout(() => {
            longPressed.current = true;
            show();
          }, LONG_PRESS_MS);
        }}
        onPointerUp={() => pressTimer.current && clearTimeout(pressTimer.current)}
        onPointerLeave={() => pressTimer.current && clearTimeout(pressTimer.current)}
        onPointerCancel={() => pressTimer.current && clearTimeout(pressTimer.current)}
        onContextMenu={(e) => e.preventDefault()}
      >
        <Current className="h-3.5 w-3.5" />
        <span>React</span>
        {total > 0 && <span className="tabular-nums text-faint">· {total}</span>}
      </button>

      <div
        id={trayId}
        role="toolbar"
        aria-label="Reactions"
        hidden={!open}
        className="absolute bottom-full right-0 z-20 mb-1.5 flex items-center gap-0.5 rounded-full bg-navy-900 px-1.5 py-1 shadow-lg shadow-navy-950/60 ring-1 ring-navy-600"
      >
        {KINDS.map(({ kind, label, Icon }) => {
          const selected = mine === kind;
          return (
            <button
              key={kind}
              type="button"
              onClick={() => pick(kind)}
              aria-pressed={selected}
              aria-label={`${label}, ${counts[kind]}${selected ? " (your reaction, press to remove)" : ""}`}
              className={`flex items-center gap-1 rounded-full px-2 py-1 text-xs transition-colors ${
                selected ? "bg-navy-700 text-ink" : "text-muted hover:bg-navy-800 hover:text-ink"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span className="tabular-nums">{counts[kind]}</span>
            </button>
          );
        })}
      </div>
      {error && (
        <p role="alert" className="absolute right-0 top-full mt-1 whitespace-nowrap text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
