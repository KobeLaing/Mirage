"use client";

import { useId, useState } from "react";

import { errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/**
 * The sign-in form. The server does the real work: it checks the password,
 * rate-limits attempts, checks the honeypot, and sets the session cookie.
 * Every failure comes back as the same "Invalid username or password" message,
 * so the form can't reveal whether a username exists.
 */
export function LoginForm() {
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const userId = useId();
  const passId = useId();
  const errorId = useId();

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      await login(
        String(form.get("username") ?? ""),
        String(form.get("password") ?? ""),
        String(form.get("website") ?? ""),
      );
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  const input =
    "mt-1 w-full rounded-xl bg-navy-900 px-3 py-2 text-ink ring-1 ring-navy-600 placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-sun";

  return (
    <form onSubmit={submit} className="space-y-4" aria-describedby={error ? errorId : undefined} noValidate>
      <div>
        <label htmlFor={userId} className="text-sm font-semibold text-muted">
          Username
        </label>
        <input id={userId} name="username" autoComplete="username" required maxLength={32} className={input} />
      </div>
      <div>
        <label htmlFor={passId} className="text-sm font-semibold text-muted">
          Password
        </label>
        <input
          id={passId}
          name="password"
          type="password"
          autoComplete="current-password"
          required
          maxLength={256}
          className={input}
        />
      </div>

      {/* HONEYPOT: a trap field for bots. People never see it: it's moved
          off-screen with CSS (.hp-field in globals.css) rather than
          type="hidden", because many bots skip hidden inputs but happily fill
          every visible-looking one. tabIndex={-1} keeps keyboard users out,
          aria-hidden keeps screen readers out, and autoComplete="off" stops the
          browser filling it. A believable name ("website") makes bots want to
          fill it. If it ever arrives with a value, the server rejects the login
          (see backend auth_service.login). */}
      <div className="hp-field" aria-hidden="true">
        <label htmlFor="website">Website</label>
        <input id="website" name="website" type="text" tabIndex={-1} autoComplete="off" defaultValue="" />
      </div>

      {error && (
        <p id={errorId} role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm font-semibold text-danger">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="w-full rounded-xl bg-sun py-2.5 font-bold text-navy-900 shadow transition hover:bg-sun-deep disabled:cursor-wait disabled:opacity-60"
      >
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
