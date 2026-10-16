# Mirage: Threat Model (as built)

STRIDE-style threat model. Written in Phase 2 (design), updated in Phase 5,
and updated again for sign-in, comments, Blind Mode, the leaderboard and the
AI Authenticity Scanner. Every mitigation points to **where it lives in the
code** and **which test proves it**. IDs refer to
[requirements.md](requirements.md) and [design.md](design.md). Paths are
relative to the repository root.

## 1. Scope

Local deployment: one FastAPI process (`backend/run.py`), one Next.js process
(`frontend/`), SQLite, and local-disk media storage. Users sign in with a
username and password; the session is a signed, httpOnly cookie backed by a
`sessions` table. Section 5 lists what must change before the app is exposed
beyond localhost.

## 2. Assets

| Asset | Why it matters |
|-------|---------------|
| A1 Vote integrity | The product is the community's AI/Real verdict. Forged or inflated votes make it worthless. |
| A2 XP, ranks and leaderboard | Status system; must reflect real participation. |
| A3 Hidden `ground_truth` | Leaking it spoils voting and lets users game any future accuracy scoring. |
| A4 User identity: passwords, sessions | Acting as someone else corrupts A1/A2 and lets an attacker delete their posts and comments. |
| A5 Uploaded media and its metadata | Users may unknowingly upload GPS location in EXIF; stored files must not become an attack vector. |
| A6 Host availability | Uploads, image decoding, password hashing and scanner analysis are the heaviest operations. |
| A7 Frontend origin | Script running in it can act as the user. |
| A8 Server internals | Stack traces, paths, and SQL are recon material. |
| A9 Supply chain | Dependencies and CI run with access to the code. |
| A10 Blind Mode answers | Counts and comments a Blind Mode user hasn't earned the right to see yet. |
| A11 Scanned files | Private uploads to the scanner; must not be stored, posted, or sent to third parties. |

## 3. Trust boundaries

```
 [TB1] Browser  ──HTTP──►  Next.js (3000)        untrusted input and files
 [TB2] Browser  ──HTTP──►  FastAPI (8000)        every request untrusted, including cookies and headers
 [TB3] FastAPI  ───────►   SQLite / disk         trusted, but fed by data crossing TB2
 [TB4] FastAPI  ──bytes──► Pillow decoder         attacker-controlled bytes into a native parser
 [TB5] Served media ─────► Browser                stored attacker content returned to other users
 [TB6] GitHub Actions ───► repo, third-party actions and packages
 [TB7] Scanner  ──bytes──► c2pa (Rust), OpenCV/FFmpeg decoders   attacker-controlled bytes into more native parsers
```

## 4. Threats, mitigations, and where they live

### S: Spoofing

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| S1 | Acting as another user without their password. | Identity comes only from the session cookie, resolved in one dependency. The cookie is a random 32-byte secret signed with `SESSION_SECRET` (itsdangerous) and expires after 4 h. The DB stores only its SHA-256 and checks expiry and revocation. The old `X-User-Id` header is gone. The app refuses to start without a ≥32-character secret. | `backend/app/api/deps.py` `get_current_user()`; `backend/app/security/tokens.py`; `backend/app/services/auth_service.py` `resolve()`; `backend/app/config.py` `_strong_secret` | `test_http.py::test_forged_or_malformed_session_cookie_is_401`, `::test_old_dev_identity_header_is_ignored`, `::test_settings_refuse_missing_or_weak_session_secret`, `test_auth.py::test_expired_session_is_rejected` |
| S2 | A request names another user (`user_id`, `voter_id`, author) to act for them. | Writes take identity only from the dependency. Every request schema uses `extra="forbid"`. Avatar and Blind Mode writes are `/me/...` only. | `backend/app/schemas/common.py` `StrictModel`; `backend/app/api/v1/users.py` | `test_votes.py::test_body_cannot_name_another_user_or_set_xp`, `test_comments.py::test_body_cannot_name_another_author`, `test_blind_mode.py::test_blind_mode_body_is_strict` |
| S3 | Cross-site request forgery: another site makes a signed-in browser vote, post, comment or delete. | Three layers: the cookie is `SameSite=Lax`; every POST/PUT/DELETE must carry an `Origin` equal to `FRONTEND_ORIGIN`; and an `X-CSRF-Token` = HMAC(session cookie). The token lives only in page memory. CORS allows credentials for that one origin only. | `backend/app/api/deps.py` `csrf_protect()`; `backend/app/security/tokens.py` `csrf_for()`; `backend/app/main.py` (CORSMiddleware) | `test_auth.py::test_write_without_csrf_token_is_blocked`, `::test_write_with_wrong_csrf_token_is_blocked`, `::test_write_from_another_origin_is_blocked`, `::test_csrf_token_from_another_session_is_rejected`, `::test_login_requires_our_origin`, `test_http.py::test_cors_allows_only_frontend_origin` |
| S4 | Password guessing (brute force, credential stuffing). | Login rate limits per IP (30/15 min) and per username (10/15 min). Argon2id hashing makes offline cracking expensive. One generic error for every failure. Failed attempts are logged with username and IP, never the password. | `backend/app/api/deps.py` `check_login_rate()`; `backend/app/security/passwords.py` | `test_auth.py::test_login_is_rate_limited_per_username`, `::test_login_is_rate_limited_per_ip`, `::test_failed_login_is_logged_without_the_password` |
| S5 | Username enumeration through login responses. | Identical status, code and message for unknown user, wrong password and honeypot. An unknown user still runs a full Argon2 verify against a dummy hash, so timing matches. | `backend/app/services/auth_service.py` `login()`; `backend/app/security/passwords.py` `verify()` | `test_auth.py::test_every_login_failure_looks_identical` |
| S6 | Bots auto-filling the login form. | **Honeypot**: a hidden `website` field (off-screen CSS, `tabIndex=-1`, `aria-hidden`, `autoComplete=off`). The server rejects any non-empty value with the generic error before checking the password, and logs `auth.suspected_bot`. Rate limits still apply. | `frontend/components/LoginForm.tsx`, `frontend/app/globals.css` `.hp-field`; `backend/app/services/auth_service.py` `login()` | `test_auth.py::test_honeypot_filled_is_rejected_like_a_wrong_password`, `::test_honeypot_empty_allows_normal_login` |
| S7 | Session theft or replay. | `HttpOnly` (no script access), `Secure`, `SameSite=Lax`, 4 h lifetime. Logout revokes the row server-side, so a copied cookie stops working. | `backend/app/api/v1/auth.py`; `backend/app/services/auth_service.py` `logout()` | `test_auth.py::test_login_sets_a_hardened_session_cookie`, `::test_logout_revokes_the_session_server_side` |

### T: Tampering

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| T1 | Vote stuffing by repeating or racing requests. | DB `UNIQUE(user_id, post_id)`; idempotent set/remove; a lost race is rolled back and retried as an update; per-user rate limit. | `backend/alembic/versions/0001_initial.py`; `backend/app/services/vote_service.py` `set_vote()` | `test_votes.py::test_repeating_the_same_vote_does_not_double_count`, `::test_concurrent_insert_race_counts_once` |
| T2 | XP farming (vote/unvote, post/delete, comment spam). | Unvote −10, switch ±0, delete post −20. Each XP change shares its action's transaction. **Comments earn no XP.** | `vote_service.py`, `post_service.py`, `comment_service.py`; `backend/app/progression.py` | `test_votes.py::test_vote_toggle_farming_nets_zero`, `::test_vote_and_xp_roll_back_together`, `test_comments.py::test_commenting_earns_no_xp` |
| T3 | Client sends XP, rank, counts, or ground truth. | No request schema has those fields; extra fields → 422. | `backend/app/schemas/` | `test_profiles.py::test_xp_cannot_be_set_through_any_endpoint` |
| T4 | Changing or deleting another user's vote, reaction, post or comment. | Keyed by the current user; post and comment delete check the owner on the server → 403. | `vote_service.py`, `reaction_service.py`, `post_service.py`, `comment_service.py` `delete_comment()` | `test_votes.py::test_user_cannot_change_another_users_vote`, `test_posts_api.py::test_cannot_delete_someone_elses_post`, `test_comments.py::test_cannot_delete_someone_elses_comment` |
| T5 | SQL injection. | Bound parameters only; AST test bans raw SQL in `app/`; Bandit. | `backend/app/repositories/` | `test_architecture.py` |
| T6 | Path traversal via filename or media key. | Client filename discarded; random keys; strict regex; resolved path must stay in the upload root. | `backend/app/storage/` | `test_upload_security.py::test_media_route_rejects_bad_or_unknown_keys` |
| T7 | Stored XSS via caption or comment. | Rendered as React text nodes only; `react/no-danger` + `innerHTML` lint bans; nonce CSP. Comments ≤ 500 chars, no control characters. | `frontend/components/PostCard.tsx`, `CommentSection.tsx`; `backend/app/schemas/comments.py` | `test_posts_api.py::test_caption_html_is_stored_as_plain_text`, `test_comments.py::test_html_is_stored_as_plain_text`, `::test_control_characters_rejected` |
| T8 | A malicious file is stored and later rendered as active content. | Magic-byte allow-list; images re-encoded; MP4 structure check; media served with `nosniff` + sandbox CSP. | `backend/app/media/`; `backend/app/api/v1/media.py` | `test_upload_security.py::test_disallowed_file_type_rejected`, `::test_media_served_with_safe_headers` |
| T9 | A migration destroys data (SQLite table rebuild cascading deletes). | Migrations add columns in place; Alembic's env turns SQLite FK enforcement off while migrating, then runs `foreign_key_check`. | `backend/alembic/env.py`; `backend/alembic/versions/0005_blind_mode.py` | `test_migrations.py::test_migrations_never_lose_existing_data` |

### R: Repudiation

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| R1 | A user denies actions; no trail. | JSON log per request with request ID and the **authenticated** user ID, plus events: `auth.login`, `auth.login_failed`, `auth.suspected_bot`, `auth.logout`, `csrf.*`, `vote.set`, `comment.created/deleted`, `scanner.scanned`, `rate_limited`. | `backend/app/logging_setup.py`, `backend/app/middleware.py` | `test_auth.py::test_failed_login_is_logged_without_the_password` |

### I: Information disclosure

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| I1 | `ground_truth` leaks. | Absent from every response schema. | `backend/app/schemas/` | `test_ground_truth.py` walks every GET route |
| I2 | Uploaded photos leak GPS or device info. | Posted images are re-encoded without metadata. **Gap:** video metadata kept. Scanner files are never stored. | `backend/app/media/sanitize.py` | `test_upload_security.py::test_uploaded_image_has_no_exif_or_gps` |
| I3 | Errors leak internals. | Generic `internal_error` + request ID; validation errors don't echo input. | `backend/app/middleware.py`, `backend/app/errors.py` | `test_http.py::test_unhandled_error_hides_internals` |
| I4 | Secrets committed to the repo. | `SESSION_SECRET` and seed passwords come only from `backend/.env` (gitignored); `.env.example` has placeholders; tests generate a random key at runtime; passwords stored only as Argon2id hashes; Gitleaks in CI. | `.gitignore`, `backend/.env.example`, `backend/scripts/seed.py`, `backend/tests/conftest.py` | `test_seed.py::test_seed_stores_only_password_hashes`, `::test_seed_refuses_to_run_without_passwords`; Gitleaks clean on all committable files |
| I5 | Clickjacking. | `X-Frame-Options: DENY` + `frame-ancestors 'none'`. | `backend/app/middleware.py`; `frontend/next.config.ts` | `test_http.py::test_security_headers_on_api_responses` |
| I6 | Profiles reveal how a user voted. | **By design.** Hidden in Blind Mode for posts the viewer hasn't voted on. | `backend/app/services/activity_service.py` | `test_blind_mode.py::test_profile_activity_hides_other_peoples_votes` |
| I7 | **Blind Mode bypass via developer tools or direct API calls.** | Enforced server-side in one rule (`is_hidden`). Counts, reactions, caption and comment count are sent as `null`; the comments and reactions endpoints return 403; vote responses hide counts after an unvote. | `backend/app/services/blind_mode.py`, `post_views.py`, `vote_service.py`, `reaction_service.py`, `comment_service.py` | `test_blind_mode.py` (all), incl. `::test_counts_and_comments_absent_before_voting` (asserts the raw response text) |
| I8 | **Scanned files leak** (stored, posted, or sent to a third party). | Validated into a temp dir that is deleted in `finally`, even if a detector crashes; no DB row or storage write. All detection is local. The registry refuses off-device detectors unless enabled **and** keyed. | `backend/app/services/scanner_service.py`; `backend/app/scanner/registry.py` | `test_scanner.py::test_scanned_file_is_deleted_and_never_posted`, `::test_file_is_deleted_even_when_a_detector_crashes`, `::test_scan_makes_no_network_connections`, `::test_off_device_detector_fails_safe_without_api_key` |
| I9 | **SSRF through C2PA remote manifests.** A file can reference a remote manifest URL that the server would fetch. | Remote manifest and OCSP fetching disabled in the c2pa settings; manifests that aren't embedded are ignored. | `backend/app/scanner/detectors/c2pa_detector.py` | `test_scanner.py::test_scan_makes_no_network_connections` |

### D: Denial of service

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| D1 | Huge uploads (posts or scans). | Streaming body limit on both upload routes; per-type limits after sniffing; JSON bodies ≤ 64 KB. | `backend/app/middleware.py`; `backend/app/main.py` `upload_paths` | `test_upload_security.py::test_oversized_body_cut_off_before_parsing`, `test_scanner.py::test_size_limit` |
| D2 | Decompression bomb. | `MAX_IMAGE_PIXELS` + warning escalated to error, for posts and scans. | `backend/app/media/sanitize.py` `verify()` | `test_media_pipeline.py::test_decompression_bomb_rejected` |
| D3 | Floods on votes, reactions, comments, scans, logins. | Per-user sliding windows (comments 10/min, scans 20/h); logins per IP and per username. **Gap:** in-memory per process. | `backend/app/ratelimit.py`; `backend/app/api/deps.py` | `test_comments.py::test_comment_rate_limit_is_per_user`, `test_scanner.py::test_scan_rate_limit_is_per_user`, `test_auth.py::test_login_is_rate_limited_*` |
| D4 | Expensive feed queries. | Cursor pagination; fixed number of SQL statements per page (now 8, including comment counts). | `backend/app/services/post_views.py` | `test_feed.py::test_feed_has_no_n_plus_one` |
| D5 | **CPU-heavy scans** (long or huge videos, big images). | Frame-sampled (≤12 frames, ≤8 flow pairs, seeks capped at 20 000 frames); pixel analysis on ≤1024 px centre crops; metadata reads capped at 8 MB; per-user scan limit. | `backend/app/scanner/frames.py`, `analysis.py`, `detectors/video_container.py` | `test_scanner.py::test_scan_rate_limit_is_per_user` |
| D6 | Login used as a CPU sink (Argon2 is deliberately slow). | Rate limits run **before** hashing; password length capped at 256. | `backend/app/api/v1/auth.py`; `backend/app/schemas/auth.py` | `test_auth.py::test_login_is_rate_limited_per_ip` |

### E: Elevation of privilege

| ID | Threat | Mitigation | Code | Tests |
|----|--------|-----------|------|-------|
| E1 | An uploaded file is executed on the server. | Never passed to a shell; stored outside the app package. | `backend/app/storage/local.py` | Bandit |
| E2 | An exploit in a native decoder (TB4, TB7). | Sniffing and structure checks before any decoder. Pillow opened with one expected format. Scanner parsers (c2pa, OpenCV/FFmpeg) only see files that passed validation. All pinned and audited. **Residual:** codec zero-days. | `backend/app/media/`; `backend/app/scanner/` | `test_scanner.py::test_same_type_checks_as_posts` |
| E3 | Compromised dependency, CI action or downloaded model. | Pinned deps; pip-audit/npm audit; Dependabot; SHA-pinned actions. The YuNet model download is HTTPS-only and SHA-256-pinned. | `backend/requirements*.txt`, `.github/workflows/ci.yml`, `backend/scripts/fetch_models.py` | CI |
| E4 | Script injection on the frontend origin. | No `dangerouslySetInnerHTML`; nonce CSP with `'strict-dynamic'`. Even with XSS, the session cookie is httpOnly. | `frontend/proxy.ts`, `frontend/eslint.config.mjs` | Phase 4 CSP check |

## 5. Known gaps and accepted risks

1. **No account lifecycle.** There is no sign-up, password change, reset or
   MFA. Accounts come from the seed script. Before exposure, add these and a
   breached-password check.
2. **Username lockout.** The per-username login limit lets an attacker keep
   a known user locked out for 15 minutes at a time. Accepted for a demo;
   production should add CAPTCHA or proof-of-work after N failures instead
   of a hard block.
3. **The rate limiter is in-memory and per process.** It resets on restart.
   Fix: a Redis-backed `RateLimiter`. Behind a reverse proxy, `client_ip()`
   must read the proxy's forwarded header.
4. **No content moderation.** No report, takedown, or admin role, for posts
   or comments.
5. **Videos are not transcoded.** Their metadata is kept on posted videos.
6. **Media URLs are unauthenticated.** They're guarded by random 128-bit
   keys, so anyone with a URL can fetch the file.
7. **Scanner limitations.** The pixel detectors are heuristics with low
   weights and can't produce a verdict alone. The C2PA signer isn't checked
   against a trust list (a "camera" claim is weighed, not trusted). Decoding
   untrusted video with FFmpeg (via OpenCV) adds native attack surface.
8. **Face-swap detection** has no bundled model; it's off by default.
9. **Uploads are fully received before the post/scan rate limit runs.**
   FastAPI parses the body before dependencies. Bounded by the size cap.
10. **No HTTPS locally.** Production must terminate TLS and add HSTS.
11. **Dev-only dependency advisory.** `braces` via `eslint-config-next`;
    lint-time only, never at runtime.
12. **Deleting an old post** removes the current `XP_PER_POST` (20), even if
    it was created under the old 25-XP rule. XP is floored at 0.
