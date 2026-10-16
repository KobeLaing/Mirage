import type { Metadata } from "next";
import { connection } from "next/server";

import { AppShell } from "@/components/AppShell";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mirage: AI or real?",
  description: "Post images and videos you suspect are AI-generated. The community votes: AI or Real.",
  icons: { icon: { url: "/logo.svg", type: "image/svg+xml" } },
};

// Explicit props type: Next's generated `LayoutProps` global only exists after
// `next dev`/`next build` has run, which a fresh CI checkout hasn't done.
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Render per request so Next.js can attach the CSP nonce from proxy.ts to its scripts.
  await connection();
  return (
    <html lang="en">
      <body className="min-h-screen bg-navy-900 antialiased">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
