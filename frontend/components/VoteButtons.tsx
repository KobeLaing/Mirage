"use client";

import { useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { VoteCounts, VoteState, VoteValue } from "@/lib/types";
import { CheckCircleIcon, RobotIcon } from "./icons";

interface VoteButtonsProps {
  postId: number;
  /** null in Blind Mode until the user votes: no counts, no result bar. */
  votes: VoteCounts | null;
  myVote: VoteValue | null;
  onVoted?: (state: VoteState) => void;
}

function optimistic(votes: VoteCounts | null, from: VoteValue | null, to: VoteValue | null): VoteCounts | null {
  if (!votes) return null; // nothing to adjust: the server decides what to reveal
  const next = { ...votes };
  if (from) next[from === "AI" ? "ai" : "real"] -= 1;
  if (to) next[to === "AI" ? "ai" : "real"] += 1;
  return next;
}

/**
 * The primary action on every post (FR-20..25). Clicking your current choice
 * removes it; clicking the other switches. The server's response is the truth.
 */
export function VoteButtons({ postId, votes: initialVotes, myVote: initialMine, onVoted }: VoteButtonsProps) {
  const { userId, applyStanding } = useAuth();
  const [votes, setVotes] = useState(initialVotes);
  const [mine, setMine] = useState(initialMine);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function choose(value: VoteValue) {
    if (userId == null || pending) return;
    const target = mine === value ? null : value;
    const before = { votes, mine };
    setVotes(optimistic(votes, mine, target));
    setMine(target);
    setPending(true);
    setError(null);
    try {
      const state = target ? await api.vote(postId, target) : await api.unvote(postId);
      setVotes(state.votes);
      setMine(state.my_vote);
      applyStanding(state.me);
      onVoted?.(state);
    } catch (err) {
      setVotes(before.votes);
      setMine(before.mine);
      setError(errorMessage(err));
    } finally {
      setPending(false);
    }
  }

  const total = votes ? votes.ai + votes.real : 0;
  const button = (value: VoteValue) => {
    const selected = mine === value;
    const isAI = value === "AI";
    const count = votes ? (isAI ? votes.ai : votes.real) : null;
    const tone = isAI
      ? selected
        ? "bg-ai text-navy-950 ring-ai shadow-[0_0_0_3px_rgba(56,189,248,0.25)]"
        : "bg-navy-900 text-ai ring-ai/50 hover:bg-ai/10 hover:ring-ai"
      : selected
        ? "bg-real text-navy-950 ring-real shadow-[0_0_0_3px_rgba(52,211,153,0.25)]"
        : "bg-navy-900 text-real ring-real/50 hover:bg-real/10 hover:ring-real";
    return (
      <button
        type="button"
        onClick={() => choose(value)}
        disabled={userId == null}
        aria-pressed={selected}
        aria-label={`Vote ${isAI ? "AI" : "Real"}${selected ? " (your vote, press to remove)" : ""}${
          count === null ? "" : `, ${count} ${count === 1 ? "vote" : "votes"}`
        }`}
        className={`flex min-w-[6.5rem] flex-1 items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-[15px] font-extrabold ring-2 transition sm:flex-none disabled:cursor-not-allowed disabled:opacity-50 ${tone}`}
      >
        {isAI ? <RobotIcon className="h-5 w-5" /> : <CheckCircleIcon className="h-5 w-5" />}
        <span>{isAI ? "AI" : "Real"}</span>
        {count !== null && <span className="rounded-md bg-navy-950/20 px-1.5 text-sm tabular-nums">{count}</span>}
      </button>
    );
  };

  return (
    <div>
      <div className="flex items-center gap-3" role="group" aria-label="Is this AI-generated or real?">
        {button("AI")}
        {button("REAL")}
      </div>
      {votes && total > 0 && (
        <div className="mt-2 flex h-1.5 w-full max-w-[16rem] overflow-hidden rounded-full bg-navy-700" aria-hidden="true">
          <div className="bg-ai" style={{ width: `${(votes.ai / total) * 100}%` }} />
          <div className="bg-real" style={{ width: `${(votes.real / total) * 100}%` }} />
        </div>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
