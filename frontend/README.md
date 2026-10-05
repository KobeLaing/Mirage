# Mirage frontend

Next.js 16 (App Router) + TypeScript + Tailwind. It talks to the backend only
through the REST API at `NEXT_PUBLIC_API_URL`.

See the [root README](../README.md) for setup. In short: `npm ci`, then `npm run dev`.

- `app/`: pages (feed `/`, profile `/users/[id]`)
- `components/`: PostCard, PostComposer, VoteButtons, ReactionBar, RankBadge, Avatar, …
- `lib/`: typed API client, dev account context, types
- `proxy.ts`: per-request nonce Content-Security-Policy
- `public/logo.svg`: logo and favicon
