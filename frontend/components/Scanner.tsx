"use client";

import { useId, useRef, useState } from "react";

import { api, errorMessage } from "@/lib/api";
import type { ScanResult, ScanSignal } from "@/lib/types";
import { ACCEPT, precheck } from "@/lib/upload";
import { ScanIcon } from "./icons";

const VERDICT_STYLE: Record<ScanResult["verdict"], string> = {
  likely_ai: "bg-ai/15 text-ai ring-ai/40",
  likely_real: "bg-real/15 text-real ring-real/40",
  inconclusive: "bg-navy-700 text-ink ring-navy-600",
};

function SignalRow({ signal }: { signal: ScanSignal }) {
  const value =
    signal.status === "ok" && signal.score !== null
      ? `${signal.score}%`
      : signal.status === "unavailable"
        ? "not run"
        : signal.status === "error"
          ? "failed"
          : "no signal";
  return (
    <li className="rounded-lg bg-navy-900 px-2.5 py-2">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-semibold text-ink">{signal.label}</span>
        <span className={`shrink-0 tabular-nums ${signal.conclusive ? "font-bold text-sun" : "text-faint"}`}>{value}</span>
      </div>
      <p className="mt-0.5 text-[11px] leading-snug text-muted">{signal.explanation}</p>
    </li>
  );
}

/**
 * Private AI check: the file is analysed on the server and deleted straight
 * after. It is never posted to the feed or stored.
 */
export function Scanner() {
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();

  async function run(file: File | null) {
    if (!file || busy) return;
    const problem = precheck(file);
    setResult(null);
    setError(problem);
    if (problem) return;
    setBusy(true);
    try {
      setResult(await api.scan(file));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <section aria-labelledby="scanner-heading" className="rounded-2xl bg-navy-800 p-3.5 ring-1 ring-navy-700">
      <h2 id="scanner-heading" className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-sun">
        <ScanIcon className="h-4 w-4" /> AI Authenticity Scanner
      </h2>
      <p className="mt-1.5 text-xs text-muted">
        Check an image or video privately. It isn&apos;t posted, and it&apos;s deleted as soon as the scan ends.
      </p>

      <label
        htmlFor={inputId}
        className={`mt-2.5 flex cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-navy-600 px-3 py-3 text-sm font-semibold text-muted transition-colors hover:border-sun hover:text-ink focus-within:border-sun ${
          busy ? "pointer-events-none opacity-60" : ""
        }`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          void run(e.dataTransfer.files?.[0] ?? null);
        }}
      >
        {busy ? "Scanning…" : "Choose a file to scan"}
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={ACCEPT}
          className="sr-only"
          disabled={busy}
          onChange={(e) => void run(e.target.files?.[0] ?? null)}
        />
      </label>

      <div aria-live="polite">
        {error && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {error}
          </p>
        )}
        {result && (
          <div className="mt-3">
            <div className={`rounded-xl px-3 py-2.5 text-center ring-1 ${VERDICT_STYLE[result.verdict]}`}>
              {result.score !== null ? (
                <>
                  <p className="text-3xl font-black tabular-nums">{result.score}%</p>
                  <p className="text-sm font-bold">
                    AI probability · {result.verdict_label}
                  </p>
                </>
              ) : (
                <>
                  <p className="text-2xl font-black">Inconclusive</p>
                  <p className="text-xs">No signal was strong enough to give a meaningful score.</p>
                </>
              )}
            </div>
            <ul className="mt-2.5 space-y-1.5" aria-label="Signals">
              {result.signals.map((s) => (
                <SignalRow key={s.detector} signal={s} />
              ))}
            </ul>
            <p className="mt-2.5 rounded-lg border border-sun/30 bg-sun/5 px-2.5 py-2 text-[11px] leading-snug text-sun">
              {result.notice}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
