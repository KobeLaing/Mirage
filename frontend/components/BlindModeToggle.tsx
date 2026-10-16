"use client";

import { useId, useRef, useState } from "react";

import { errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { EyeOffIcon } from "./icons";

/**
 * Blind Mode switch. Turning it ON asks for confirmation first; turning it
 * OFF happens straight away. The setting is saved on the server, which is
 * also where the hiding happens (see backend app/services/blind_mode.py).
 */
export function BlindModeToggle() {
  const { blindMode, setBlindMode } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descId = useId();

  async function apply(enabled: boolean) {
    setBusy(true);
    setError(null);
    try {
      await setBlindMode(enabled);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="blind-heading" className="rounded-2xl bg-navy-800 p-3.5 ring-1 ring-navy-700">
      <div className="flex items-center gap-3">
        <h2 id="blind-heading" className="flex flex-1 items-center gap-2 text-sm font-bold uppercase tracking-wider text-sun">
          <EyeOffIcon className="h-4 w-4" /> Blind Mode
        </h2>
        <button
          type="button"
          role="switch"
          aria-checked={blindMode}
          aria-labelledby="blind-heading"
          disabled={busy}
          onClick={() => (blindMode ? apply(false) : dialogRef.current?.showModal())}
          className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
            blindMode ? "bg-sun" : "bg-navy-600"
          }`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-navy-950 shadow transition-all ${
              blindMode ? "left-[1.375rem]" : "left-0.5"
            }`}
            aria-hidden="true"
          />
        </button>
      </div>
      <p className="mt-1.5 text-xs text-muted">
        {blindMode
          ? "On: vote before you see counts and comments."
          : "Vote without seeing what everyone else thinks."}
      </p>
      {error && (
        <p role="alert" className="mt-1.5 text-xs text-danger">
          {error}
        </p>
      )}

      {/* Native <dialog>: focus trapping and Esc-to-cancel come from the browser. */}
      <dialog
        ref={dialogRef}
        aria-labelledby={titleId}
        aria-describedby={descId}
        className="fixed inset-0 m-auto h-fit w-[min(24rem,calc(100vw-2rem))] rounded-2xl bg-navy-800 p-5 text-ink shadow-2xl ring-1 ring-navy-600 backdrop:bg-navy-950/75 backdrop:backdrop-blur-sm"
      >
        <h3 id={titleId} className="text-lg font-bold">
          Enter Blind Mode?
        </h3>
        <p id={descId} className="mt-2 text-sm text-muted">
          Vote counts and comments will be hidden until you vote on each post.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            className="rounded-xl px-4 py-2 text-sm font-semibold text-muted ring-1 ring-navy-600 hover:text-ink"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              dialogRef.current?.close();
              void apply(true);
            }}
            className="rounded-xl bg-sun px-5 py-2 text-sm font-bold text-navy-900 hover:bg-sun-deep"
          >
            Yes
          </button>
        </div>
      </dialog>
    </section>
  );
}
