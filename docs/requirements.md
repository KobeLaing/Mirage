# Mirage — Requirements

Phase 1 of the secure SDLC. This document restates what Mirage must do, the
security properties it must hold, and the ways we expect people to try to
abuse it. Each requirement has an ID so the design, threat model, and tests
can refer back to it.

Status: **approved** (decisions recorded in §7).

## 1. Product summary

Mirage is a social platform where users post images and videos they suspect
are AI-generated, and the community votes on whether each post is **AI** or
**Real**. Voting earns XP, XP earns verifier ranks, and ranks show as medals.

Scope for this version: a local side project. It runs with one command per
service (backend, frontend). It has no real authentication: a header account
switcher picks one of two seeded users. The design must let real auth,
object storage, and PostgreSQL drop in later without rewriting routes or
business logic.

## 2. Functional requirements

### 2.1 Accounts and identity
| ID | Requirement |
|----|-------------|
| FR-1 | Two seeded accounts exist: a Silver Verifier with 150 XP and a Gold Verifier with 600 XP. |
| FR-2 | The header has an account switcher that lets the person at the keyboard act as either seeded user. |
| FR-3 | The backend resolves the "current user" in exactly one dependency, so real auth can replace it without touching routes. |
| FR-4 | Each user has a display name, an avatar chosen from 10 original cartoon SVG avatars, XP, and a derived rank. |
| FR-5 | A user can change their own avatar, and only their own. |

### 2.2 Feed (home page)
| ID | Requirement |
|----|-------------|
| FR-10 | A post composer sits at the top of the feed: one image or one video per post, with an optional caption. |
| FR-11 | Below the composer, community posts are listed newest first. |
| FR-12 | The feed uses cursor-based pagination ("load more" / infinite scroll). |
| FR-13 | Media is lazy-loaded. Videos never autoplay with sound (muted, user-initiated playback, controls shown). |
| FR-14 | The feed has distinct loading, empty, and error states. |
| FR-15 | A user can delete their own posts, and only their own. |

### 2.3 Voting (primary action)
| ID | Requirement |
|----|-------------|
| FR-20 | Each post has two vote buttons: **AI** (small robot icon) and **Real** (check mark in a circle). |
| FR-21 | Each button shows its current count. |
| FR-22 | A user has at most one vote per post. AI and Real are mutually exclusive. |
| FR-23 | A user can switch their vote (AI ↔ Real) or remove it. |
| FR-24 | Repeating the same vote request does not change counts or XP (idempotent). |
| FR-25 | Voting is visually the main action on every post. |

### 2.4 Reactions (secondary action)
| ID | Requirement |
|----|-------------|
| FR-30 | Three reactions: heart, like, laugh, using original icons and an original design. |
| FR-31 | The reaction bar is hidden by default. It appears on hover over a small "React" control, on keyboard focus, and on long-press on touch devices. |
| FR-32 | The reaction bar is smaller and more muted than the vote buttons. |
| FR-33 | **One reaction per user per post.** A user can change it to a different reaction or remove it. Reaction counts are shown. |
| FR-34 | Reactions do not earn XP (keeps the XP economy tied to verification work). |

### 2.5 Profile page (top to bottom)
| ID | Requirement |
|----|-------------|
| FR-40 | Header block: name, avatar, verifier rank with badge, and an XP progress bar toward the next rank (full bar with a "max rank" label at Palladium). |
| FR-41 | The same post composer component as the feed. |
| FR-42 | Recent activity: posts this user voted on, each labeled with their vote (AI or Real), plus the user's own posts, newest first. |
| FR-43 | Avatar picker showing the 10 avatars. Only shown on your own profile. |
| FR-44 | The profile has loading, empty, and error states. |

### 2.6 Ranks and XP
| ID | Requirement |
|----|-------------|
| FR-50 | Ranks, low to high, with XP thresholds: Bronze 0, Silver 100, Gold 300, Platinum 700, Palladium 1500. A user holds a rank at exactly its threshold (e.g. 100 XP = Silver, 99 XP = Bronze). |
| FR-51 | +10 XP per vote cast. +25 XP per post created. |
| FR-52 | Removing a vote removes its 10 XP. Switching a vote (AI ↔ Real) is neutral: still one vote, still 10 XP. |
| FR-53 | Deleting your own post removes its 25 XP. Other users keep the XP from their votes on it. |
| FR-54 | XP and rank values live in one backend config file. |
| FR-55 | XP is computed only on the server. No endpoint accepts XP from the client. |
| FR-56 | XP never goes below 0. |
| FR-57 | The badge is one SVG component taking `rank` as a prop: a medal in the rank color, hanging from a ribbon with three vertical stripes (blue, red, blue). All five medal colors are clearly distinguishable. |

### 2.7 Visual design
| ID | Requirement |
|----|-------------|
| FR-60 | Feed and profile share one color scheme: navy background, warm golden-yellow header (changed from amber/orange after Phase 5). |
| FR-61 | Logo and favicon: a cute square robot crossed by crisp horizontal glitch/heat-shimmer distortion lines. Recognizable, not blurry. One SVG used for both. |
| FR-62 | Reusable components: post card, composer, vote buttons, reaction bar, badge, avatar. |

### 2.8 Seed data
| ID | Requirement |
|----|-------------|
| FR-70 | A seed script creates the two accounts and six caption-less posts, and copies media from `/seed-media` into backend upload storage. |
| FR-71 | Images: `aiphote1.jpg` (AI), `Phoenix_Sun.jpg` (AI), `sandy-hook.png` (REAL). Videos (placeholders, replaced later): `ai-video-1.mp4` (AI), `ai-video-2.mp4` (AI), `real-video-1.mp4` (REAL). |
| FR-72 | Each seeded post stores `ground_truth` as a hidden field. It is never displayed and never returned by the public API. |
| FR-73 | The seed script is safe to re-run (it resets to a known state rather than duplicating data). |
| FR-74 | Seeded media goes through the same validation and metadata stripping as user uploads. If a file is missing, that post is skipped with a clear warning. |

## 3. Non-functional requirements (system design)

| ID | Requirement |
|----|-------------|
| NFR-1 | **Layering.** Routes (HTTP only) → services (business rules) → repositories (all DB access). No business logic in routes, no SQL outside repositories. |
| NFR-2 | **Stateless API.** No server-side session state. Versioned under `/api/v1`. |
| NFR-3 | **Data integrity in the DB.** Unique `(user_id, post_id)` on votes and on reactions; foreign keys everywhere; check constraints on enums and XP ≥ 0. A vote and its XP change commit in one transaction. |
| NFR-4 | **Feed performance.** Cursor pagination on `(created_at, id)` descending with a matching index. Counts loaded with aggregate queries, not one query per post. |
| NFR-5 | **Media abstraction.** A small storage interface with a local-disk implementation, swappable for object storage. |
| NFR-6 | **Portability.** Nothing SQLite-specific in models, migrations, or queries. Switching to PostgreSQL means changing `DATABASE_URL`. |
| NFR-7 | **Reliability.** One JSON error shape for every error; correct HTTP status codes; idempotent vote endpoints. |
| NFR-8 | **Operability.** Structured (JSON) logs, `GET /health`, all config from environment variables. |
| NFR-9 | **Simplicity.** No microservices, queues, or caches. Deferred practices leave a clean seam. |
| NFR-10 | **Run locally** with one command per service. |

## 4. Security requirements

| ID | Requirement |
|----|-------------|
| SR-1 | **Upload type allow-list.** Images: JPEG, PNG, GIF. Videos: MP4. Anything else (including WebP and WebM) is rejected with 415. |
| SR-2 | **Content sniffing.** The type is determined from the file's magic bytes on the server. Client `Content-Type` and file extension are not trusted for the decision. |
| SR-3 | **Size limits.** Images 10 MB, videos 50 MB (configurable). Enforced while streaming, so an oversized upload is cut off without being fully read into memory. Rejected with 413. |
| SR-4 | **Random filenames.** Stored files get a server-generated random name plus an extension derived from the detected type. The original filename is never used in a path. |
| SR-5 | **Safe storage location.** Uploads live in a data directory outside the application package and outside any directory served as code. |
| SR-6 | **Never served as HTML.** Media responses set the detected `Content-Type`, `X-Content-Type-Options: nosniff`, and a locked-down CSP (`default-src 'none'; sandbox`). Only allow-listed types can be stored, so nothing renderable as HTML/SVG exists. |
| SR-7 | **Metadata stripping.** Images are re-encoded server-side, removing EXIF (including GPS) and other metadata. |
| SR-8 | **Input validation.** Every request body, query, and path parameter is validated by Pydantic (types, lengths, enums). Caption ≤ 500 characters; control characters rejected. |
| SR-9 | **No string-built SQL.** All queries go through SQLAlchemy expressions with bound parameters. Bandit checks for this in CI. |
| SR-10 | **Captions rendered as text.** The frontend never uses `dangerouslySetInnerHTML` for user content. |
| SR-11 | **Server-side authorization.** Every write checks the acting user may do it. Users can only change their own votes, reactions, posts, and avatar. Votes and reactions are always keyed to the resolved current user, never to a user ID from the request. |
| SR-12 | **Rate limits per user**: 10 posts/hour, 120 votes/minute, 120 reactions/minute (configurable). Exceeding returns 429 with `Retry-After`. |
| SR-13 | **CORS** allows only the configured frontend origin. |
| SR-14 | **Security headers** on every API response: `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` plus `frame-ancestors 'none'`, and `Referrer-Policy`. The frontend sets its own CSP and frame restrictions. |
| SR-15 | **No secrets in code.** Config from environment; a `.env.example` documents every variable; Gitleaks in CI. |
| SR-16 | **No internal details in errors.** Unhandled exceptions return a generic 500 in the standard error shape with a request ID; the stack trace goes only to the server log. |
| SR-17 | **Hidden fields stay hidden.** `ground_truth` is excluded by the response schemas themselves (allow-list serialization), not by deleting it afterwards. |
| SR-18 | **Dependencies.** Pinned versions, only real and maintained packages, each justified. pip-audit and npm audit in CI. Dependabot for pip and npm. |
| SR-19 | **CI with least privilege.** GitHub Actions workflow with `permissions: contents: read`. |
| SR-20 | **Server-owned XP.** No API field accepts XP, rank, counts, or ground truth from the client (Pydantic models forbid extra fields). |

## 5. Abuse cases

| ID | Abuse case | Attack | Countermeasure |
|----|-----------|--------|----------------|
| AC-1 | **Vote stuffing** | Send the same vote many times, or race parallel requests, to inflate a count. | DB unique `(user_id, post_id)` (NFR-3); idempotent upsert (FR-24); rate limit (SR-12). |
| AC-2 | **XP farming by toggling** | Vote, remove, vote again in a loop to bank XP. | Removing a vote removes its XP (FR-52), so the loop nets zero. |
| AC-3 | **XP farming by switching** | Flip AI ↔ Real repeatedly hoping each switch pays. | Switching is XP-neutral (FR-52). |
| AC-4 | **XP farming by posting** | Post, delete, repost for +25 each time; or spam uploads. | Deleting a post removes its XP (FR-53); post rate limit (SR-12). Gap: no duplicate-media detection. |
| AC-5 | **Client-supplied XP** | Add `"xp": 99999` to a request body. | No endpoint accepts XP; Pydantic `extra="forbid"` (SR-20); XP only changes inside services (FR-55). |
| AC-6 | **Acting as another user** | Put another user's ID in a body or URL to vote, react, delete, or change avatar on their behalf. | Writes use only the resolved current user (SR-11); avatar endpoint is `/me/avatar`; post deletion checks ownership (403). |
| AC-7 | **Impersonation via the dev identity header** | Set `X-User-Id` to any user. | Accepted risk while there is no real auth: the switcher *is* impersonation by design. Contained to one dependency (FR-3). Known gap #1. |
| AC-8 | **Malicious upload: HTML/SVG/script** | Upload `evil.html` renamed `cat.jpg`, or an SVG with script, hoping it is served and executed on the app's origin. | Magic-byte detection (SR-2); SVG not allow-listed (SR-1); `nosniff` + forced `Content-Type` + sandboxing CSP on media (SR-6). |
| AC-9 | **Malicious upload: polyglot / parser exploit** | A file that is both a valid JPEG and something else, or a crafted image targeting the decoder. | Images re-encoded (SR-7), which drops trailing payloads; Pillow decompression-bomb limit; pinned, audited Pillow (SR-18). Gap: videos are not transcoded. |
| AC-10 | **Path traversal** | Filename `../../app/main.py`, or a media URL containing `..`. | Original filename never used (SR-4); media keys validated against a strict pattern before touching disk. |
| AC-11 | **Resource exhaustion via uploads** | Very large files, or many uploads, to fill disk or memory. | Streaming size limits (SR-3); post rate limit (SR-12); decompression-bomb guard. |
| AC-12 | **Ground-truth leak** | Read API responses, error messages, or the frontend bundle to learn which posts are AI. | Response schemas never include the field (SR-17); a test asserts it is absent from every endpoint; frontend has no knowledge of it. |
| AC-13 | **Stored XSS via caption** | Caption `<img src=x onerror=...>`. | Captions rendered as text (SR-10); frontend CSP (SR-14). |
| AC-14 | **SQL injection** | Inject through cursor, caption, or path params. | Parameterized SQLAlchemy only (SR-9); cursor decoded and validated as typed data. |
| AC-15 | **Cross-origin abuse** | A malicious site makes the user's browser call the API. | CORS restricted (SR-13). With no cookies there is no ambient credential to ride; when real auth arrives, use bearer tokens or SameSite cookies + CSRF protection. |
| AC-16 | **Clickjacking** | Frame the app to trick a user into voting. | `X-Frame-Options: DENY` / `frame-ancestors 'none'` (SR-14). |
| AC-17 | **Information disclosure via errors** | Trigger exceptions to read stack traces, file paths, or SQL. | Generic 500 body with request ID (SR-16). |
| AC-18 | **Rate-limit evasion via user switching** | Switch identities to reset per-user limits. | Accepted for now (two seeded users, dev feature). Real auth closes this; a per-IP backstop is a noted seam. |
| AC-19 | **Supply-chain attack** | Typosquatted or compromised package. | Minimal, pinned, justified deps; lockfiles; pip-audit, npm audit, Dependabot (SR-18). |

## 6. Assumptions and out of scope

- **No real authentication.** Identity is a trusted `X-User-Id` header set by the switcher. Must be replaced before any public deployment.
- **No content moderation.** No reporting, takedown, or review of uploads. Must be added before any public deployment.
- **Single instance.** The rate limiter is in-process memory, behind an interface so a shared store can replace it for multiple instances.
- **Videos are validated but not transcoded,** so their metadata is not stripped (that needs ffmpeg, a large system dependency). Listed gap.
- **Ground truth is stored, not used.** No scoring or "reveal" yet. It is a seam for a future accuracy-based XP bonus.
- **Votes are public.** A user's profile shows how they voted. That is the requested feature; noted as a privacy consideration.

## 7. Decisions (resolved at Phase 1 approval)

1. **Reactions:** one reaction per user per post; the user can change or remove it. DB unique `(user_id, post_id)`.
2. **Post deletion:** included, owner only. Deleting removes the author's +25 XP; voters keep their vote XP.
3. **Limits:** images 10 MB, videos 50 MB; 10 posts/hour, 120 votes/min, 120 reactions/min; caption ≤ 500 chars; types JPEG, PNG, GIF, MP4 (WebP and WebM removed after Phase 5).
4. **Location:** project lives at `C:\Users\thela\Projects\Mirage` (Documents is protected by Controlled Folder Access).
