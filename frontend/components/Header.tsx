"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useCurrentUser } from "@/lib/currentUser";
import { AccountSwitcher } from "./AccountSwitcher";

export function Header() {
  const { userId } = useCurrentUser();
  const pathname = usePathname();
  const navLink = (href: string, label: string) => {
    const active = pathname === href;
    return (
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        className={`rounded-full px-3 py-1.5 text-sm font-bold transition-colors ${
          active ? "bg-navy-900 text-sun" : "text-navy-900 hover:bg-navy-900/10"
        }`}
      >
        {label}
      </Link>
    );
  };

  return (
    <header className="sticky top-0 z-30 bg-gradient-to-r from-sun to-sun-deep shadow-lg shadow-navy-950/40">
      <div className="mx-auto flex max-w-2xl items-center gap-3 px-4 py-2.5">
        <Link href="/" className="flex items-center gap-2.5" aria-label="Mirage home">
          {/* eslint-disable-next-line @next/next/no-img-element -- the logo is a static local SVG */}
          <img src="/logo.svg" alt="" width={40} height={40} className="drop-shadow" />
          <span className="text-xl font-black tracking-tight text-navy-900">Mirage</span>
        </Link>
        <nav className="ml-2 hidden items-center gap-1 sm:flex" aria-label="Main">
          {navLink("/", "Feed")}
          {userId != null && navLink(`/users/${userId}`, "My profile")}
        </nav>
        <div className="ml-auto">
          <AccountSwitcher />
        </div>
      </div>
    </header>
  );
}
