"use client";

import { usePathname } from "next/navigation";

import { LOGIN_PATH, useAuth } from "@/lib/auth";
import { Header } from "./Header";
import { SidePane } from "./SidePane";
import { ErrorState } from "./states";

function Splash() {
  return (
    <div role="status" aria-live="polite" className="flex min-h-[60vh] items-center justify-center">
      <span className="sr-only">Loading</span>
      {/* eslint-disable-next-line @next/next/no-img-element -- static local SVG */}
      <img src="/logo.svg" alt="" width={56} height={56} className="animate-pulse opacity-80" />
    </div>
  );
}

/**
 * Decides what to render based on the session: the login page for signed-out
 * visitors, the full app for signed-in users, and a splash screen while we're
 * still finding out (or while a redirect is in flight).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { status, retry } = useAuth();
  const pathname = usePathname();
  const onLogin = pathname === LOGIN_PATH;

  if (status === "error") {
    return (
      <main className="mx-auto max-w-xl px-4 pt-10">
        <ErrorState error={new Error("Can't reach the Mirage server.")} onRetry={retry} />
      </main>
    );
  }
  if (onLogin) {
    return <main className="px-4 pb-16">{status === "signedOut" ? children : <Splash />}</main>;
  }
  if (status !== "signedIn") return <Splash />;

  return (
    <>
      <Header />
      {/* Side pane first in the DOM (and on top on small screens), then the page. */}
      <div className="mx-auto flex max-w-6xl flex-col gap-5 px-4 pb-16 pt-5 lg:flex-row lg:items-start">
        <aside
          aria-label="Side panel"
          className="lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:w-80 lg:shrink-0 lg:overflow-y-auto"
        >
          <SidePane />
        </aside>
        <main className="min-w-0 max-w-xl flex-1">{children}</main>
      </div>
    </>
  );
}
