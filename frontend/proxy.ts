import { NextResponse, type NextRequest } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Set by the API at login. Cookies are scoped by host, not port, so the API on
// localhost:8000 and this app on localhost:3000 share it. (Use the same host
// name for both: "localhost" and "127.0.0.1" are different cookie hosts.)
const SESSION_COOKIE = "mirage_session";
const LOGIN_PATH = "/login";

/**
 * Runs before every page request and does two things:
 *
 * 1. Sign-in gate. Without a session cookie, every page except /login
 *    redirects to /login before any page code is sent. This only checks that
 *    the cookie exists: it can't verify the signature (that needs the API's
 *    secret). The API verifies the session on every request, so a fake cookie
 *    gets you an empty shell that can't load any data.
 *
 * 2. Per-request nonce-based Content-Security-Policy (SR-14). Next.js reads the
 *    nonce from this header and attaches it to its own scripts, so no inline
 *    script without the nonce can run.
 */
export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname !== LOGIN_PATH && !request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.redirect(new URL(LOGIN_PATH, request.url));
  }

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const isDev = process.env.NODE_ENV === "development";
  const api = new URL(API_URL).origin;

  const csp = [
    "default-src 'self'",
    // 'unsafe-eval' only in development (React's dev tooling needs it).
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' ${isDev ? "'unsafe-inline'" : `'nonce-${nonce}'`}`,
    // Inline style *attributes* (progress bar widths, media aspect ratios) can't
    // carry a nonce. Allowing them can't run script; <style> blocks still need the nonce.
    "style-src-attr 'unsafe-inline'",
    `img-src 'self' data: blob: ${api}`,
    `media-src 'self' blob: ${api}`,
    `connect-src 'self' ${api}`,
    "font-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!_next/static|_next/image|logo.svg|avatars).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
