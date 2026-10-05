# Mirage: Threat Model (as built)

STRIDE-style threat model. Written in Phase 2 (design) and updated in Phase 5
so every mitigation points to **where it lives in the code** and **which test
proves it**. IDs refer to [requirements.md](requirements.md) and
[design.md](design.md). Paths are relative to the repository root.

## 1. Scope

Local deployment: one FastAPI process (`backend/run.py`), one Next.js process
(`frontend/`), SQLite, and local-disk media storage. There is no real
authentication: the account switcher sends `X-User-Id`. Section 5 lists what
must change before the app is exposed beyond localhost.

## 2. Assets

| Asset | Why it matters |
|-------|---------------|
| A1 Vote integrity | The product is the community's AI/Real verdict. Forged or inflated votes make it worthless. |
| A2 XP and ranks | Status system; must reflect real participation. |
| A3 Hidden `ground_truth` | Leaking it spoils voting and lets users game any future accuracy scoring. |
| A4 User identity | Acting as someone else corrupts A1/A2 and lets an attacker delete their posts. |
| A5 Uploaded media and its metadata | Users may unknowingly upload GPS location in EXIF; stored files must not become an attack vector. |
| A6 Host availability | Uploads and image decoding are the heaviest operations. |
| A7 Frontend origin | Script running in it can act as the user. |
| A8 Server internals | Stack traces, paths, and SQL are recon material. |
| A9 Supply chain | Dependencies and CI run with access to the code. |

## 3. Trust boundaries

```
 [TB1] Browser  ──HTTP──►  Next.js (3000)        untrusted input and files
 [TB2] Browser  ──HTTP──►  FastAPI (8000)        every request untrusted, including X-User-Id
 [TB3] FastAPI  ───────►   SQLite / disk         trusted, but fed by data crossing TB2
 [TB4] FastAPI  ──bytes──► Pillow decoder         attacker-controlled bytes into a native parser
 [TB5] Served media ─────► Browser                stored attacker content returned to other users
 [TB6] GitHub Actions ───► repo, third-party actions and packages
```

## 4. Threats, mitigations, and where they live

### S: Spoofing

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| S1 | Anyone sends `X-User-Id: 2` and acts as user 2. | **Accepted for local dev** (gap #1). Identity is resolved in exactly one function, so real auth replaces one function body. Malformed or unknown IDs → 401. Settings refuse `AUTH_MODE=dev_header` in production. | `backend/app/api/deps.py` `_identify()`, `get_current_user()`; `backend/app/config.py` `_no_dev_auth_in_production` | `test_http.py::test_unknown_or_malformed_user_header_is_401`, `::test_production_refuses_dev_header_identity` |
| S2 | A request names another user (`user_id`, `voter_id`) to act for them. | Writes take identity only from the dependency. Every request schema uses `extra="forbid"`, so unknown fields → 422. Avatar change is only `/me/avatar`. | `backend/app/schemas/common.py` `StrictModel`; `backend/app/api/v1/users.py` | `test_votes.py::test_body_cannot_name_another_user_or_set_xp`, `::test_query_string_cannot_name_another_user`, `test_profiles.py::test_cannot_change_someone_elses_avatar` |
| S3 | A malicious site calls the API from the user's browser. | CORS allows only `FRONTEND_ORIGIN`, no credentials. No cookies, so no ambient credential to ride. | `backend/app/main.py` (CORSMiddleware) | `test_http.py::test_cors_allows_only_frontend_origin` |

### T: Tampering

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| T1 | Vote stuffing by repeating or racing requests. | DB `UNIQUE(user_id, post_id)`; idempotent set/remove; an `IntegrityError` from a lost race is rolled back and retried as an update; per-user rate limit. | `backend/alembic/versions/0001_initial.py` (`uq_votes_user_post`); `backend/app/services/vote_service.py` `set_vote()` | `test_votes.py::test_repeating_the_same_vote_does_not_double_count`, `::test_concurrent_insert_race_counts_once`, `test_migrations.py::test_db_rejects_duplicate_vote` |
| T2 | XP farming (vote/unvote loops, switching, post/delete loops). | Unvote −10, switch ±0, delete post −25. Each XP change runs in the same transaction as its action, via an atomic SQL update floored at 0. | `backend/app/services/vote_service.py`, `post_service.py` `delete_post()`; `backend/app/repositories/user_repo.py` `add_xp()`; `backend/app/progression.py` | `test_votes.py::test_vote_toggle_farming_nets_zero`, `::test_switching_moves_counts_without_changing_xp`, `::test_vote_and_xp_roll_back_together`, `test_posts_api.py::test_delete_own_post_removes_xp_and_file` |
| T3 | Client sends XP, rank, counts, or ground truth. | No request schema has those fields; extra fields → 422. | `backend/app/schemas/` | `test_profiles.py::test_xp_cannot_be_set_through_any_endpoint` |
| T4 | Changing or deleting another user's vote, reaction, or post. | Votes and reactions are keyed by the current user only. Post delete checks `author_id` → 403. | `vote_service.py`, `reaction_service.py`, `post_service.py` `delete_post()` | `test_votes.py::test_user_cannot_change_another_users_vote`, `test_reactions.py::test_users_cannot_touch_each_others_reactions`, `test_posts_api.py::test_cannot_delete_someone_elses_post` |
| T5 | SQL injection through cursor, caption, or IDs. | SQLAlchemy expressions with bound parameters only. The cursor is decoded into a typed Pydantic model. An AST test bans raw SQL and query building outside repositories. Bandit in CI. | `backend/app/repositories/`; `post_service.py` `decode_cursor()` | `test_architecture.py` (all), `test_feed.py::test_bad_cursor_is_400` |
| T6 | Path traversal via filename or media key. | The client filename is discarded; keys are 32 random hex characters plus an extension. Keys are matched against a strict regex, and the resolved path must stay inside the upload root. | `backend/app/storage/base.py` `KEY_PATTERN`; `backend/app/storage/local.py` `_path()` | `test_upload_security.py::test_media_route_rejects_bad_or_unknown_keys`, `test_posts_api.py::test_stored_filename_is_random` |
| T7 | Stored XSS via caption. | Captions render as React text nodes only (`whitespace-pre-wrap`). ESLint `react/no-danger` and an `innerHTML` ban fail the build. Nonce CSP. | `frontend/components/PostCard.tsx`; `frontend/eslint.config.mjs`; `frontend/proxy.ts` | `test_posts_api.py::test_caption_html_is_stored_as_plain_text`; lint rule verified in Phase 4 by a deliberately bad file |
| T8 | A malicious file is stored and later executed or rendered as active content. | Magic-byte allow-list (no SVG/HTML). Images re-encoded. MP4 box structure checked. Media served with a fixed `Content-Type`, `nosniff`, and `CSP: default-src 'none'; sandbox`. Files stored outside the app package. | `backend/app/media/sniff.py`, `sanitize.py`, `pipeline.py`; `backend/app/api/v1/media.py` `MEDIA_HEADERS` | `test_upload_security.py::test_disallowed_file_type_rejected`, `::test_media_served_with_safe_headers`, `test_media_pipeline.py::test_mp4_with_appended_junk_rejected` |

### R: Repudiation

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| R1 | A user denies votes or posts; no trail to investigate abuse. | JSON log line per request (request ID, user ID, method, path, status, duration), plus domain events: `vote.set`, `post.created`, `post.delete_forbidden`, `upload.rejected`, `rate_limited`. Votes keep created/updated timestamps. **Partial:** with dev-header identity, logs show the *claimed* user. | `backend/app/logging_setup.py`, `backend/app/middleware.py` `RequestContextMiddleware` | `test_http.py::test_request_id_is_echoed_when_valid` |

### I: Information disclosure

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| I1 | `ground_truth` leaks through the API. | Absent from every response schema (allow-list serialization). The frontend types don't have it. | `backend/app/db/models.py` (comment on the column); `backend/app/schemas/`; `frontend/lib/types.ts` | `test_ground_truth.py` walks **every GET route in the OpenAPI schema** plus write responses, errors, and the OpenAPI doc itself |
| I2 | Uploaded photos leak GPS or device info. | Images re-encoded with EXIF orientation applied, then all metadata dropped (EXIF, XMP, comments, text chunks; the colour profile is kept). Seeded media goes through the same pipeline. **Gap:** video metadata is kept. | `backend/app/media/sanitize.py`; `backend/scripts/seed.py` | `test_media_pipeline.py::test_exif_and_gps_are_stripped`, `test_upload_security.py::test_uploaded_image_has_no_exif_or_gps`, `test_seed.py::test_seed_strips_image_metadata` |
| I3 | Errors leak stack traces, SQL, or paths. | Unhandled exceptions are caught in middleware → generic `internal_error` + request ID; the traceback goes only to the server log. `debug=False`. Validation errors list fields and never echo input. OpenAPI docs are disabled in production. | `backend/app/middleware.py`; `backend/app/errors.py`; `backend/app/main.py` | `test_http.py::test_unhandled_error_hides_internals`, `::test_validation_errors_do_not_echo_input` |
| I4 | Secrets committed to the repo. | No secrets exist; config comes from env vars; `.env` is gitignored; `.env.example` files hold safe defaults only. Gitleaks runs in CI over full history. | `.gitignore`, `backend/.env.example`, `frontend/.env.example`, `.github/workflows/ci.yml` (`secrets` job) | Phase 4: Gitleaks clean over 20 targets; canary secret detected |
| I5 | Clickjacking. | `X-Frame-Options: DENY` + `frame-ancestors 'none'` on API and frontend. | `backend/app/middleware.py` `API_SECURITY_HEADERS`; `frontend/next.config.ts`; `frontend/proxy.ts` | `test_http.py::test_security_headers_on_api_responses` |
| I6 | Profiles reveal how a user voted. | **By design** (requested feature). Documented privacy consideration. | — | — |

### D: Denial of service

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| D1 | Huge uploads exhaust memory or disk. | The body limit is enforced while the request streams (Content-Length check plus a byte counter); per-type limits apply after sniffing (10 MB / 50 MB); JSON bodies are capped at 64 KB; 10 posts/hour. | `backend/app/middleware.py` `BodySizeLimitMiddleware`; `backend/app/media/pipeline.py` | `test_upload_security.py::test_oversized_image_rejected`, `::test_oversized_body_cut_off_before_parsing`, `::test_oversized_json_body_rejected`, `test_posts_api.py::test_post_rate_limit` |
| D2 | Decompression bomb. | `MAX_IMAGE_PIXELS` is set explicitly; the bomb *warning* is escalated to an error → 415. | `backend/app/media/sanitize.py` | `test_media_pipeline.py::test_decompression_bomb_rejected` |
| D3 | Request floods on votes and reactions. | Per-user sliding-window limits → 429 + `Retry-After`. **Gap:** in-memory per process; no per-IP limit; switching user IDs evades it. | `backend/app/ratelimit.py`; `backend/app/api/deps.py` `rate_limit()` | `test_votes.py::test_vote_rate_limit`, `test_reactions.py::test_reaction_rate_limit`, `test_ratelimit.py` |
| D4 | Expensive feed queries (N+1, deep offsets). | Cursor pagination on an index; `limit` ≤ 50; a fixed 6 SQL statements per page whatever the size. | `backend/app/repositories/post_repo.py`; `backend/app/services/post_views.py` | `test_feed.py::test_feed_has_no_n_plus_one` (counts statements), `::test_cursor_pages_cover_everything_once` |

### E: Elevation of privilege

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| E1 | An uploaded file is executed on the server. | Stored under `backend/var/uploads` (not importable, no static handler), never passed to a shell, and served only through the media route. | `backend/app/storage/local.py`; `backend/app/api/v1/media.py` | Bandit (no subprocess/exec use) |
| E2 | An exploit in the image decoder (TB4). | Sniffing runs before Pillow, which is only ever opened with the single expected format. `verify()` runs, then a fresh decode. Pillow is pinned and audited. **Residual:** a zero-day in a codec library. | `backend/app/media/sanitize.py` `reencode()` | `test_media_pipeline.py::test_corrupt_image_rejected`, `::test_trailing_payload_dropped_by_reencode` |
| E3 | A compromised dependency or CI action. | Minimal, pinned dependencies with lockfiles. pip-audit and npm audit. Dependabot (pip, npm, actions). Actions pinned by commit SHA. `permissions: contents: read`, plus `pull-requests: read` on the Gitleaks job only. `persist-credentials: false`. `npm ci --ignore-scripts`. | `backend/requirements*.txt`, `frontend/package-lock.json`, `.github/workflows/ci.yml`, `.github/dependabot.yml` | CI |
| E4 | Script injection on the frontend origin. | No `dangerouslySetInnerHTML` (lint-enforced). Per-request nonce CSP with `'strict-dynamic'` and no `'unsafe-inline'` for scripts in production. Style *attributes* are allowed (cannot run script). | `frontend/proxy.ts`, `frontend/eslint.config.mjs` | Phase 4: production build run under the CSP; no violations logged |

## 5. Known gaps and accepted risks

1. **No real authentication (S1).** Any client can claim any user ID. This is
   acceptable only on localhost. Replace `_identify()` in
   `backend/app/api/deps.py` with session or token verification (e.g. OIDC)
   before exposure. At that point add CSRF protection if cookies are used.
   Rate-limit evasion (D3) and weak repudiation (R1) follow from this gap.
2. **No content moderation.** There is no report button, takedown flow,
   abuse/CSAM hash matching, admin role, or audit of deletions. This must
   exist before any public deployment.
3. **Videos are not transcoded.** Their metadata (which can include GPS) is
   kept, and their bytes reach browsers' decoders unchanged. Only the
   container header and box structure are checked. Fix: an ffmpeg
   re-mux/transcode step in `backend/app/media/pipeline.py`.
4. **The rate limiter is in-memory and per process.** It resets on restart
   and isn't shared across instances. Fix: a Redis-backed implementation of
   the `RateLimiter` protocol. Also add a per-IP backstop.
5. **Uploads are fully received before the post rate limit is checked.**
   FastAPI parses the body before running dependencies. Bounded by the
   streaming size cap.
6. **No malware scanning of uploads.** Seam: a step in
   `post_service.create_post()` before `storage.save()`.
7. **No HTTPS locally.** Production must terminate TLS, add HSTS, and add
   `upgrade-insecure-requests` to the CSP.
8. **Provenance metadata (C2PA) is stripped** with EXIF. `Phoenix_Sun.jpg`
   carried a C2PA-style JUMBF block. Seam: verify manifests before stripping
   and store the verdict as a hidden field.
9. **Dev-only dependency advisory.** `braces` ≤ 3.0.3 (GHSA-vfj7-8cjw-p6xm,
   a ReDoS-style stack exhaustion) is reached via `eslint-config-next` →
   `fast-glob`. No patched release exists. It is only reachable through
   lint-time glob patterns that we control, never at runtime. CI fails on
   runtime-dependency findings and reports dev findings without failing.
   Re-check when Dependabot proposes an update.
10. **Deleting a seeded post** removes 25 XP from its author even though
    seeding didn't award it. XP is floored at 0.
