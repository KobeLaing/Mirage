# Mirage — Design

Phase 2 of the secure SDLC. Requirement IDs (FR, NFR, SR, AC) refer to
[requirements.md](requirements.md). Threats are in
[threat-model.md](threat-model.md).

## 1. Architecture

```
 Browser ──────────────► Next.js frontend (localhost:3000)
    │                    App Router, client components, Tailwind
    │                    Talks to the backend ONLY via REST.
    │
    │  fetch /api/v1/*  (header X-User-Id from the account switcher)
    ▼
 FastAPI backend (localhost:8000)
 ┌────────────────────────────────────────────────────────────┐
 │ Middleware: request ID → JSON access log → security        │
 │             headers → CORS (frontend origin only)          │
 │ Exception handlers → one JSON error shape                  │
 ├────────────────────────────────────────────────────────────┤
 │ API layer      app/api/v1/*.py      HTTP only: parse,      │
 │                app/api/deps.py      validate, call service, │
 │                                     map result to schema   │
 │   get_current_user()  ◄── the ONE identity seam (FR-3)     │
 │   rate_limit(action)  ◄── per-user limiter (SR-12)         │
 ├────────────────────────────────────────────────────────────┤
 │ Service layer  app/services/*.py    business rules: votes, │
 │                                     XP, ownership checks,  │
 │                                     upload pipeline,       │
 │                                     transaction boundaries │
 ├────────────────────────────────────────────────────────────┤
 │ Repositories   app/repositories/*.py  all SQLAlchemy       │
 │                                       queries live here    │
 ├──────────────────────────┬─────────────────────────────────┤
 │ SQLAlchemy 2.0 ORM       │ MediaStorage interface          │
 │ SQLite (DATABASE_URL)    │  └ LocalDiskStorage (var/uploads)│
 └──────────────────────────┴─────────────────────────────────┘
```

**One process per service.** Backend: `python run.py` (applies migrations,
then starts uvicorn). Frontend: `npm run dev`. Seed: `python -m scripts.seed`.

**Stateless (NFR-2).** Every request carries its identity (`X-User-Id`). The
server keeps no session. The only in-process state is the rate limiter's
counters, which sit behind a `RateLimiter` interface. With more than one
instance it is swapped for a shared store (e.g. Redis) without touching
routes.

### 1.1 Layer rules (NFR-1)

| Layer | May | May not |
|-------|-----|---------|
| Routes | Read path/query/body/files, call one service function, return a schema, choose status codes | Import `sqlalchemy`, compute XP, check ownership |
| Services | Enforce rules, call repositories, call `MediaStorage`, own `commit()`/`rollback()` | Build HTTP responses, write raw SQL |
| Repositories | Build SQLAlchemy `select/insert/update/delete` with bound params | Contain business rules, commit transactions |

A test (`tests/test_architecture.py`) scans the `app/api` package and fails
if any route module imports `sqlalchemy`, and scans `app/services` for
`text(`/`exec_driver_sql`. It's cheap and stops layering from eroding.

### 1.2 Identity seam (FR-3)

```python
# app/api/deps.py — the only place that knows how a user is identified
def get_current_user(x_user_id: int | None = Header(None), db = Depends(get_db)) -> User:
    # DEV ONLY: trusts the X-User-Id header set by the account switcher.
    # Replace this function body with token/session verification for real auth.
```

Routes depend on `CurrentUser`. Nothing else reads the header. Missing or
unknown ID → 401. `AUTH_MODE=dev_header` in config makes the trust explicit,
and the app refuses to start with that mode when `ENVIRONMENT=production`.

## 2. Backend layout

```
backend/
  run.py                      # alembic upgrade head + uvicorn (one command)
  requirements.txt            # pinned runtime deps
  requirements-dev.txt        # pinned test/scan deps (-r requirements.txt)
  .env.example
  alembic.ini
  alembic/versions/0001_initial.py
  app/
    main.py                   # create_app(): middleware, handlers, routers
    config.py                 # Settings (env vars, pydantic-settings)
    progression.py            # XP values + rank thresholds (FR-54) + pure fns
    logging_setup.py          # JSON log formatter
    errors.py                 # AppError subclasses + handlers (one shape)
    middleware.py             # request ID, access log, security headers
    db/
      base.py  session.py  models.py
    api/
      deps.py                 # get_db, get_current_user, get_storage, rate_limit
      health.py               # GET /health
      v1/ users.py  posts.py  votes.py  reactions.py  media.py
    schemas/                  # Pydantic request/response models
      common.py  users.py  posts.py  votes.py
    services/
      user_service.py  post_service.py  post_views.py  vote_service.py
      reaction_service.py  activity_service.py  media_service.py  health_service.py
    repositories/
      user_repo.py  post_repo.py  vote_repo.py  reaction_repo.py  maintenance_repo.py
    media/
      sniff.py                # magic-byte detection + MP4 box-structure check
      sanitize.py             # Pillow re-encode, EXIF strip
      pipeline.py             # capped copy to temp file, sniff, sanitise (uploads + seed)
    storage/
      base.py                 # MediaStorage Protocol
      local.py                # LocalDiskStorage
    ratelimit.py              # RateLimiter Protocol + InMemorySlidingWindow
  scripts/
    seed.py
  tests/
  var/                        # gitignored: mirage.db, uploads/
```

## 3. Data model

Plain SQLAlchemy types only (`Integer`, `String`, `Text`, `DateTime(timezone=True)`,
`Enum` stored as `String` + `CheckConstraint`), so the same migration runs on
SQLite and PostgreSQL (NFR-6). SQLite foreign keys are enabled with the
standard `PRAGMA foreign_keys=ON` connect hook. That hook is the single
dialect-aware line, and it runs only when the URL is SQLite.

```
users
  id            INTEGER PK
  handle        VARCHAR(32)  NOT NULL UNIQUE
  display_name  VARCHAR(64)  NOT NULL
  avatar_id     INTEGER      NOT NULL  CHECK (avatar_id BETWEEN 1 AND 10)
  xp            INTEGER      NOT NULL DEFAULT 0  CHECK (xp >= 0)
  created_at    TIMESTAMPTZ  NOT NULL

posts
  id            INTEGER PK
  author_id     INTEGER      NOT NULL  FK → users.id ON DELETE CASCADE
  caption       VARCHAR(500) NULL
  media_key     VARCHAR(64)  NOT NULL UNIQUE      -- random name, e.g. "3f9c…a1.jpg"
  media_kind    VARCHAR(8)   NOT NULL  CHECK IN ('image','video')
  mime_type     VARCHAR(32)  NOT NULL             -- from sniffing, not the client
  width/height  INTEGER      NULL                 -- images only, avoids layout shift
  ground_truth  VARCHAR(4)   NULL  CHECK IN ('AI','REAL')   -- HIDDEN (SR-17)
  created_at    TIMESTAMPTZ  NOT NULL
  INDEX ix_posts_feed (created_at, id)   -- NFR-4; scanned backwards for DESC
  INDEX ix_posts_author (author_id, created_at DESC)          -- profile activity

votes
  id            INTEGER PK
  user_id       INTEGER      NOT NULL  FK → users.id ON DELETE CASCADE
  post_id       INTEGER      NOT NULL  FK → posts.id ON DELETE CASCADE
  value         VARCHAR(4)   NOT NULL  CHECK IN ('AI','REAL')
  created_at, updated_at TIMESTAMPTZ NOT NULL
  UNIQUE uq_votes_user_post (user_id, post_id)                -- NFR-3, AC-1
  INDEX ix_votes_post (post_id)                               -- count aggregation
  INDEX ix_votes_user_recent (user_id, updated_at DESC)       -- profile activity

reactions
  id            INTEGER PK
  user_id       INTEGER      NOT NULL  FK → users.id ON DELETE CASCADE
  post_id       INTEGER      NOT NULL  FK → posts.id ON DELETE CASCADE
  kind          VARCHAR(8)   NOT NULL  CHECK IN ('heart','like','laugh')
  created_at, updated_at TIMESTAMPTZ NOT NULL
  UNIQUE uq_reactions_user_post (user_id, post_id)            -- decision §7.1
  INDEX ix_reactions_post (post_id)
```

Rank is **derived** from `xp` on read (never stored), so thresholds can change
without a data migration.

`ground_truth` lives on the `Post` ORM model but on no response schema.
Response schemas are built with `model_validate` from explicit fields, so a
new column never leaks by default.

Deferred seam: an `xp_events` ledger table (who, delta, reason, ref) for
auditing XP. Not built now; `users.xp` is updated with one atomic
`UPDATE users SET xp = CASE WHEN xp + :delta < 0 THEN 0 ELSE xp + :delta END`
statement (portable SQL, unlike SQLite's two-argument `MAX` or Postgres's
`GREATEST`), so concurrent changes can't lose updates and XP never goes
negative (FR-56).

## 4. Key flows

### 4.1 Cast or switch a vote: `PUT /api/v1/posts/{id}/vote {"value":"AI"}`

```
vote_service.set_vote(db, user, post_id, value):        # one transaction
  post = post_repo.get(post_id)              → 404 if missing
  existing = vote_repo.get(user.id, post_id)
  if existing and existing.value == value:   → no-op (idempotent, FR-24)
  elif existing:                              → update value; XP unchanged (FR-52)
  else:                                       → insert vote; user_repo.add_xp(+10)
  commit                                      # vote + XP together (NFR-3)
  on IntegrityError (lost a race on the unique constraint):
     rollback, re-read, apply the "existing" branch → still exactly one vote, one +10
  return counts + my_vote + my new xp/rank
```

`DELETE /api/v1/posts/{id}/vote`: if a vote exists, delete it and
`add_xp(-10)` in one transaction; if not, no-op. Both return 200 with the
current state, so a repeated DELETE is harmless.

Reactions use the same shape (`PUT/DELETE /posts/{id}/reaction`) without XP.

### 4.2 Create a post: `POST /api/v1/posts` (multipart: `file`, `caption?`)

```
route: rate_limit("post"), CurrentUser, UploadFile, Form(caption) → PostCreate schema
post_service.create_post(db, storage, user, upload, caption):
  1. upload.read_capped(upload, max=VIDEO_MAX)   stream 64 KB chunks to a temp file,
                                                  abort with 413 past the limit (SR-3)
  2. sniff.detect(head bytes) → (kind, mime, ext) or 415   (SR-1, SR-2)
  3. if image: enforce IMAGE_MAX (413); sanitize.reencode() (SR-7)
        - Image.open + verify(), MAX_IMAGE_PIXELS guard (AC-9, AC-11)
        - exif_transpose (keep visual orientation), then save without
          exif/icc/xmp/comments → new bytes; width/height recorded
     if video: check container structure (ftyp box / EBML header); stored as-is
  4. key = secrets.token_hex(16) + ext            (SR-4)
  5. storage.save(key, bytes_or_file)
  6. post_repo.create(...); user_repo.add_xp(+25); commit
     if the DB step fails → storage.delete(key)   (no orphaned files)
```

Delete: `post_service.delete_post` → 404 if missing, 403 if
`post.author_id != user.id`, else delete row (cascades votes/reactions),
`add_xp(-25)`, commit, then `storage.delete(key)`.

### 4.3 Feed query (NFR-4): `GET /api/v1/posts?cursor=…&limit=20`

Cursor = base64url of `{"t": created_at ISO, "id": n}`. It is decoded and
validated by a Pydantic model; garbage → 400.

```
Query 1  posts JOIN users           WHERE created_at < :t OR (created_at = :t AND id < :id)
                                    ORDER BY created_at DESC, id DESC LIMIT :limit+1
Query 2  votes      GROUP BY post_id, value   WHERE post_id IN (:page_ids)
Query 3  reactions  GROUP BY post_id, kind    WHERE post_id IN (:page_ids)
Query 4  my votes      WHERE user_id = :me AND post_id IN (:page_ids)
Query 5  my reactions  WHERE user_id = :me AND post_id IN (:page_ids)
```

Five queries per page whatever the page size. A test counts statements
with a SQLAlchemy event listener to lock this in. The `OR` form is used
instead of a row-value tuple comparison because it's portable. The
`(created_at DESC, id DESC)` index serves the `ORDER BY` and the range.

### 4.4 Profile activity: `GET /api/v1/users/{id}/activity?limit=30`

Two indexed queries: the user's last N votes (joined to posts, ordered by
`votes.updated_at`) and the user's last N posts. They are merged in the
service by timestamp, cut to N, and counts attached using the same batch
queries as the feed. Each item is `{type: "voted"|"posted", at, post, vote?}`.
A post the user both posted and voted on appears once as "posted" with their
vote shown. Seam: cursor pagination over the merged stream later.

## 5. API routes

All under `/api/v1` except `/health`. JSON only, except the media route and
the multipart upload. Every request schema uses `extra="forbid"` (SR-20).

| Method | Path | Auth | Rate limit | Success | Errors |
|--------|------|------|-----------|---------|--------|
| GET | `/health` | — | — | 200 `{status, db}` | 503 if DB unreachable |
| GET | `/users` | — | — | 200 list (for the switcher) | |
| GET | `/me` | user | — | 200 Profile | 401 |
| PUT | `/me/avatar` `{avatar_id}` | user | — | 200 Profile | 401, 422 |
| GET | `/users/{id}` | optional | — | 200 Profile | 404 |
| GET | `/users/{id}/activity?limit` | optional | — | 200 Activity[] | 404 |
| GET | `/posts?cursor&limit` | optional | — | 200 `{items, next_cursor}` | 400 bad cursor |
| POST | `/posts` multipart | user | post | 201 Post | 401, 413, 415, 422, 429 |
| GET | `/posts/{id}` | optional | — | 200 Post | 404 |
| DELETE | `/posts/{id}` | user | — | 204 | 401, 403, 404 |
| PUT | `/posts/{id}/vote` `{value}` | user | vote | 200 VoteState | 401, 404, 422, 429 |
| DELETE | `/posts/{id}/vote` | user | vote | 200 VoteState | 401, 404, 429 |
| PUT | `/posts/{id}/reaction` `{kind}` | user | react | 200 ReactionState | 401, 404, 422, 429 |
| DELETE | `/posts/{id}/reaction` | user | react | 200 ReactionState | 401, 404, 429 |
| GET | `/media/{key}` | — | — | 200 file (Range supported) | 404 |

"Optional" auth: if `X-User-Id` is present, `my_vote`/`my_reaction` are
filled in; otherwise they are `null`.

**Response shapes** (abridged):

```jsonc
// Post
{ "id": 7, "author": {"id":1,"display_name":"…","avatar_id":3,"rank":"silver"},
  "caption": null, "media": {"kind":"image","url":"http://…/api/v1/media/ab12….jpg",
  "mime_type":"image/jpeg","width":296,"height":296},
  "votes": {"ai": 4, "real": 1}, "reactions": {"heart":2,"like":0,"laugh":1},
  "my_vote": "AI", "my_reaction": null, "created_at": "…" }
// Profile
{ "id":1, "handle":"…", "display_name":"…", "avatar_id":3, "xp":150,
  "rank":{"key":"silver","name":"Silver Verifier","min_xp":100},
  "next_rank":{"key":"gold","name":"Gold Verifier","min_xp":300},
  "progress": 0.25 }                       // 0..1, 1.0 at max rank
// VoteState
{ "post_id":7, "my_vote":"AI", "votes":{"ai":5,"real":1}, "my_xp":160, "my_rank":"silver" }
// Error (every error, NFR-7)
{ "error": { "code":"rate_limited", "message":"Too many votes. Try again shortly.",
             "request_id":"9f1c…", "details": null } }
```

Status codes: 400 bad cursor; 401 no/unknown user; 403 not owner;
404 missing; 409 not used (the vote upsert absorbs conflicts); 413 too big;
415 wrong type; 422 validation (Pydantic errors mapped to
`details: [{field, message}]` without echoing input values); 429 rate
limited + `Retry-After`; 500 generic `internal_error` + request ID; 503 health.

## 6. Media storage (NFR-5)

```python
class MediaStorage(Protocol):
    def save(self, key: str, src: BinaryIO) -> None: ...
    def delete(self, key: str) -> None: ...
    def url_for(self, key: str) -> str: ...      # what the API returns to clients
    def local_path(self, key: str) -> Path | None # None for remote stores
```

- `LocalDiskStorage(root=UPLOAD_DIR)` writes to `backend/var/uploads/`. That
  is outside the `app` package and not served by any static handler (SR-5).
  `url_for` returns `{PUBLIC_API_URL}/api/v1/media/{key}`.
- Keys must match `^[0-9a-f]{32}\.(jpg|png|gif|mp4)$` before any
  filesystem call, and the resolved path must stay inside `root` (AC-10).
- The media route serves with `FileResponse` (Range support for video seeking),
  `Content-Type` looked up from the extension (which itself came from
  sniffing), plus `X-Content-Type-Options: nosniff`,
  `Content-Security-Policy: default-src 'none'; sandbox`,
  `Cross-Origin-Resource-Policy: same-site`, and
  `Cache-Control: public, max-age=31536000, immutable` (keys are random and
  never reused).
- Swap: an `S3Storage` would return pre-signed/CDN URLs from `url_for`, and the
  media route simply stops being used. The services don't change.

**Seed media and provenance.** `Phoenix_Sun.jpg` carries an embedded
provenance block (JUMBF, the container C2PA "Content Credentials" use).
Re-encoding (SR-7) strips it along with EXIF. That is consistent and safe,
but it does discard a signal that is relevant to an AI-detection app.
Future seam: read and verify C2PA manifests *before* stripping, and store
the verdict as a hidden field like `ground_truth`.

## 7. Configuration (NFR-8)

All from environment variables (with `.env` support for local dev). No
defaults contain secrets; there are no secrets at all yet.

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENVIRONMENT` | `development` | `production` refuses `AUTH_MODE=dev_header` |
| `DATABASE_URL` | `sqlite:///./var/mirage.db` | swap to `postgresql+psycopg://…` |
| `UPLOAD_DIR` | `./var/uploads` | media root |
| `PUBLIC_API_URL` | `http://localhost:8000` | base for media URLs |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | sole CORS origin |
| `AUTH_MODE` | `dev_header` | identity seam |
| `MAX_IMAGE_BYTES` / `MAX_VIDEO_BYTES` | 10 MB / 50 MB | SR-3 |
| `MAX_IMAGE_PIXELS` | 40,000,000 | decompression-bomb guard (D2) |
| `RATE_LIMIT_POSTS_PER_HOUR` | 10 | SR-12 |
| `RATE_LIMIT_VOTES_PER_MINUTE` | 120 | SR-12 |
| `RATE_LIMIT_REACTIONS_PER_MINUTE` | 120 | SR-12 |
| `LOG_LEVEL` | `INFO` | |
| `SEED_MEDIA_DIR` | `../seed-media` | seed script |

Frontend: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

XP values and rank thresholds are *game rules*, not deployment config. They
live in `app/progression.py` (FR-54) as one frozen table, so a typo in an
env var can't change the economy.

## 8. Cross-cutting

- **Logging:** stdlib `logging` with a JSON formatter. One access line per
  request: `ts, level, request_id, method, path, status, duration_ms, user_id`.
  Domain events (`vote.set`, `post.created`, `rate_limited`, `upload.rejected`
  with reason) are logged at INFO/WARNING. Captions, file contents, and
  headers other than the user ID are never logged.
- **Request ID:** generated per request (or accepted from `X-Request-ID` if it
  is a valid UUID), returned in the response header and in error bodies.
- **Errors:** an `AppError(code, message, status)` hierarchy is raised by
  services; handlers map it, plus `RequestValidationError`, `HTTPException`,
  and bare `Exception`, to the one error shape. The bare handler logs the
  traceback with the request ID and returns only `internal_error` (SR-16).
  FastAPI `debug=False` always; `/docs` and `/openapi.json` are enabled only
  in development.
- **Security headers (SR-14)** on all API responses:
  `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-site`.
  The `/docs` page gets a relaxed CSP in development only.
- **CORS (SR-13):** `allow_origins=[FRONTEND_ORIGIN]`, methods
  `GET, POST, PUT, DELETE`, headers `Content-Type, X-User-Id, X-Request-ID`,
  no credentials (there are no cookies).
- **Rate limiting (SR-12):** `rate_limit("vote")` dependency →
  `RateLimiter.hit(f"{user_id}:vote", limit, window)` → 429 + `Retry-After`.
  It runs after identity resolution, so the key is the authenticated user.
  An in-memory sliding window, thread-safe, is reset between tests.

## 9. Frontend design

Next.js App Router, TypeScript (strict), Tailwind. Pages are thin server
components that render client components. All data comes from the REST API
at runtime, because identity lives in the browser (the switcher).

```
frontend/
  app/
    layout.tsx           # <Header/>, CurrentUserProvider, navy theme, favicon
    page.tsx             # Feed: <PostComposer/> + <Feed/>
    users/[id]/page.tsx  # Profile: <ProfileHeader/> <PostComposer/> <ActivityList/>
  public/logo.svg        # header logo AND favicon (one file, FR-61)
  proxy.ts               # per-request nonce CSP
  components/
    Header.tsx           # yellow header, <Logo/>, nav, <AccountSwitcher/>
    Logo.tsx             # glitch robot SVG
    AccountSwitcher.tsx  # lists GET /users, stores choice in localStorage
    PostComposer.tsx     # file picker + preview + caption + submit; shared
    Feed.tsx             # cursor pagination, IntersectionObserver "load more"
    PostCard.tsx         # author, media, caption (text only), votes, reactions
    PostMedia.tsx        # <img loading="lazy"> / <video muted playsInline preload="metadata" controls>
    VoteButtons.tsx      # AI (robot) + Real (check-in-circle), counts, aria-pressed
    ReactionBar.tsx      # quiet "React" trigger; hover/focus/long-press reveal
    RankBadge.tsx        # <RankBadge rank="gold"/>: medal + blue/red/blue ribbon
    XpProgressBar.tsx
    Avatar.tsx           # <Avatar id={1..10}/>, 10 inline SVG faces
    AvatarPicker.tsx     # own profile only, inside a dialog opened by clicking your avatar
    ProfileHeader.tsx
    ActivityList.tsx     # "Voted AI" / "Voted Real" / "Posted" labels
    states/ LoadingState.tsx  EmptyState.tsx  ErrorState.tsx
    icons/ RobotIcon  CheckCircleIcon  HeartIcon  LikeIcon  LaughIcon  TrashIcon
  lib/
    api.ts               # typed fetch wrapper; parses the error shape; sends X-User-Id
    types.ts             # mirrors API schemas (no ground_truth anywhere)
    currentUser.tsx      # React context + localStorage
```

**Interaction details:**
- **Votes:** clicking your current choice removes the vote; clicking the other
  one switches. Optimistic update, rolled back if the request fails; the
  server's returned counts are authoritative. Buttons are full-size, high
  contrast, with labels "AI" and "Real" next to the icons.
- **Reactions:** a small muted "React" pill. The bar opens on `mouseenter`
  (with a short close delay so it can be reached), on `focus-within`, and
  after a 450 ms touch hold (`pointerdown` timer, cancelled on move or up).
  Esc closes it. The bar uses `role="toolbar"` with `aria-label`s. The icons
  are original line-art glyphs, deliberately not in the style of any
  existing platform's reaction set.
- **Videos:** `muted`, no `autoplay`, `preload="metadata"`, `controls`. They
  pause when scrolled off-screen.
- **Media layout:** width/height from the API reserve space (no layout jump).
- **Captions:** rendered as `{caption}` text nodes only. ESLint bans
  `dangerouslySetInnerHTML` via `react/no-danger`.
- **States:** skeleton cards while loading, "No posts yet, be the first"
  empty state, and an error card with the request ID and a Retry button.

**Palette (FR-60):** background navy `#0B1A33`, surface `#132648`, raised
`#1B3360`, text `#E8EEF8`, muted `#93A4C3`. Header light yellow `#FFE680` →
`#FFD95A` gradient with navy text; the same yellow is used for the primary
button, focus rings, and highlights (changed from amber/orange on request). AI accent cyan `#38BDF8`, Real accent
green `#34D399` (contrast ≥ 4.5:1 on the surface).

**Medal colors (FR-57)**, picked to differ in hue *and* lightness so they read
as distinct even for common color-vision deficiencies:

| Rank | Base | Shine | Notes |
|------|------|-------|-------|
| Bronze | `#A0522D` | `#D08A5A` | warm brown |
| Silver | `#B8C2CC` | `#EEF2F6` | cool light grey |
| Gold | `#E8B004` | `#FFE27A` | saturated yellow |
| Platinum | `#7FD3D8` | `#D9FAFB` | pale icy teal (distinct from silver) |
| Palladium | `#6B5BD6` | `#B9AEFF` | deep violet with a sheen (top rank stands out) |

Each medal also carries an embossed rank number (1–5) for non-color cueing.
The ribbon is three vertical stripes: blue `#1E4FD8`, red `#D62839`, blue.

**Frontend CSP** (as built: a per-request **nonce** set in `proxy.ts`, the
Next 16 replacement for middleware): `default-src 'self'`;
`script-src 'self' 'nonce-…' 'strict-dynamic'` (+ `'unsafe-eval'` only in
dev); `style-src 'self' 'nonce-…'` (`'unsafe-inline'` in dev only);
`style-src-attr 'unsafe-inline'` (style *attributes* for bar widths and
aspect ratios; they cannot run script); `img-src`/`media-src`/`connect-src`
limited to self + the API origin; `frame-ancestors 'none'`;
`object-src 'none'`; `base-uri 'self'`; `form-action 'self'`. Static headers
in `next.config.ts`: `X-Frame-Options: DENY`, `nosniff`,
`Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`.
Every page is rendered per request so the nonce can be applied.
The original plan of `'unsafe-inline'` scripts with a nonce seam was upgraded
during the build because Next 16 supports nonces directly.

**As-built deviations from this design** (all minor):
- The feed index is ascending `(created_at, id)`; B-trees scan it backwards
  for `DESC`, so a descending index adds nothing on either database.
- Caption length (500) is a schema constant matching the DB column, not an env var.
- The favicon and header logo are one file, `public/logo.svg`.

## 10. Testing strategy

| Area | Tests |
|------|-------|
| Progression | `rank_for_xp` at 0, 99, 100, 299, 300, 699, 700, 1499, 1500, 10_000; progress fractions (150 → 0.25, 600 → 0.75); max-rank progress = 1.0; negative input rejected |
| Votes | first vote +10; same vote again → counts and XP unchanged; switch → counts move, XP unchanged; remove → −10; remove again → no change; DB rejects a duplicate `(user, post)` insert directly; vote on missing post → 404 |
| Reactions | set, change, remove, repeat; one per user per post |
| Posts | create image/video; caption optional; caption too long → 422; delete own → −25 and file removed; delete other's → 403 |
| Feed | newest first; cursor pages don't overlap or skip (including equal timestamps); bad cursor → 400; **statement count stays 5** for 1 vs 20 posts |
| Security | disallowed type (HTML renamed .jpg, SVG, PDF) → 415; oversized → 413; EXIF/GPS removed from a JPEG; User B can't alter User A's vote (and `user_id` in a body → 422); `ground_truth` absent from every endpoint's JSON (walks all routes against a seeded DB); unknown `X-User-Id` → 401; media key traversal → 404; security headers present; CORS rejects another origin; 500 body has no traceback; rate limit → 429 + `Retry-After` |
| Architecture | no `sqlalchemy` import in `app/api`; no raw `text()` SQL in services |
| Frontend | `next lint` + `tsc --noEmit` in CI. Component tests are a deferred seam; no test runner is added, to keep dependencies minimal. |

Tests run on a temporary SQLite file and temp upload dir per test session,
with Alembic migrations applied, so the migrations themselves are tested.

## 11. Dependencies (SR-18)

All pinned exactly. Versions are resolved to current releases at build time
and checked with pip-audit and npm audit before Phase 3 ends.

**Backend runtime**

| Package | Why |
|---------|-----|
| `fastapi` | Required web framework; brings `pydantic` and `starlette`. |
| `uvicorn` | ASGI server to run FastAPI. Installed without `[standard]` extras to avoid pulling in unneeded packages. |
| `sqlalchemy` | Required ORM; parameterized queries. |
| `alembic` | Required migrations. |
| `pydantic-settings` | Typed, validated config from env vars and `.env`; part of the Pydantic project. |
| `python-multipart` | FastAPI's required parser for `multipart/form-data` file uploads. |
| `pillow` | Image decoding/verification, re-encoding to strip EXIF/GPS (SR-7), dimensions. |

**Backend dev/CI**

| Package | Why |
|---------|-----|
| `pytest` | Required test runner. |
| `httpx` | Required by FastAPI's `TestClient`. |
| `bandit` | Python static security analysis (CI requirement). |
| `pip-audit` | Dependency vulnerability audit (CI requirement). |

Deliberately **not** added: `python-magic` (needs native libmagic on
Windows; our allow-list is small enough for an explicit magic-byte table),
`slowapi` (IP-keyed by default and less actively maintained; a ~40-line
limiter keyed on the user fits better), `structlog` (stdlib JSON formatter
is enough), any icon library (all icons are original SVGs).

**Frontend:** `next`, `react`, `react-dom`, `typescript`, `tailwindcss`
(+ its PostCSS plugin), `eslint` + `eslint-config-next`, and `@types/*`. This
is exactly what `create-next-app` installs for a TypeScript + Tailwind
project. Nothing else.

**CI tools** (not app deps): `gitleaks/gitleaks-action` pinned by commit
SHA; `actions/checkout`, `actions/setup-python`, and `actions/setup-node`
pinned by SHA.

## 12. Toolchain

- **Python 3.12** (this machine has 3.9, which is end-of-life and no longer
  supported by current FastAPI/Pillow releases).
- **Node.js 24 LTS** (installed during Phase 3; 24 is the current LTS line).
- `.python-version` and `.nvmrc` pin these; CI uses the same versions.

## 13. Build increments (Phase 3)

| Step | Delivers | Tests that must pass |
|------|----------|----------------------|
| a | config, models, migration 0001, storage, media pipeline, seed + placeholder videos | migration up/down, seed idempotency, progression unit tests |
| b | posts API (create/list/get/delete), media route, error format, headers, health; frontend shell, header, switcher, composer, feed, post card | posting, upload security, feed pagination + query count, ground-truth leak |
| c | vote + reaction APIs; VoteButtons, ReactionBar | voting rules, authz, rate limits |
| d | users/me/avatar/activity APIs; profile page, RankBadge, XP bar, avatars | profile + activity tests |
| e | logo/favicon, palette polish, states, accessibility pass | full suite + lint + typecheck |

Then CI workflow, Dependabot, SECURITY.md, scans (Phase 4), and README and
threat-model update (Phase 5).
