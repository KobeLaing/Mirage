# Mirage

A social platform where people post images and videos they suspect are
AI-generated, and the community votes: **AI** or **Real**. Voting earns XP,
XP earns verifier ranks (Bronze → Silver → Gold → Platinum → Palladium), and
ranks show as medals.

It's a local side project, built with a secure SDLC so it can grow without
a rewrite:

- [Requirements and abuse cases](docs/requirements.md)
- [Design](docs/design.md)
- [Threat model](docs/threat-model.md)

```
backend/     FastAPI + SQLAlchemy + Alembic + SQLite   (routes → services → repositories)
frontend/    Next.js 16 (App Router) + TypeScript + Tailwind
seed-media/  images/videos used by the seed script
docs/        requirements, design, threat model
```

## Prerequisites

- **Python 3.12+**
- **Node.js 24 LTS**

(Both were installed with winget during setup on this machine.)

## Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt # or requirements.txt for runtime only
copy .env.example .env              # optional: defaults work as-is
python -m scripts.seed              # create the 2 demo users and 6 demo posts (safe to re-run)
python run.py                       # ONE command: migrates, then serves on http://localhost:8000
```

- `python run.py --reload` auto-reloads on code changes.
- Health check: <http://localhost:8000/health>
- API docs (development only): <http://localhost:8000/docs>
- Data lives in `backend/var/` (SQLite DB and uploads). Delete it and re-seed to start fresh.

## Frontend

```powershell
cd frontend
npm ci
copy .env.example .env.local        # optional: points at http://localhost:8000
npm run dev                         # ONE command: http://localhost:3000
```

Use the **"Acting as"** switcher in the header to switch between the two
seeded users:

- **Kobe Laing** (@Kobe): Silver Verifier, 150 XP (¼ of the way to Gold)
- **Kara Mercer** (@KaraM): Gold Verifier, 600 XP (¾ of the way to Platinum)

## Tests and security checks

The same checks run in CI (`.github/workflows/ci.yml`) on every push and pull request.

| Check | Command (from `backend/` or `frontend/`) |
|-------|------------------------------------------|
| Backend tests (166) | `python -m pytest` |
| Python static analysis | `python -m bandit -c pyproject.toml -r app scripts run.py` |
| Python dependency audit | `python -m pip_audit -r requirements.txt -r requirements-dev.txt --strict` |
| Frontend lint | `npm run lint` |
| Frontend type check | `npm run typecheck` |
| npm dependency audit | `npm audit --omit=dev --audit-level=high` |
| Secret scan | CI (Gitleaks). Locally: `gitleaks dir .` |

## Replacing the placeholder videos

`seed-media/ai-video-1.mp4`, `ai-video-2.mp4`, and `real-video-1.mp4` are
4-second silent placeholders. Overwrite them with real MP4s (H.264, ≤ 50 MB),
keeping the same file names, then re-run `python -m scripts.seed`. Seeded
media goes through the same validation as user uploads, so a file that isn't
a real MP4 is skipped with a warning.

## Dependencies and why each is there

**Backend runtime** (`backend/requirements.txt`, fully pinned)

| Package | Why |
|---------|-----|
| fastapi | Required web framework (brings pydantic and starlette) |
| uvicorn | ASGI server (installed without extras) |
| SQLAlchemy | Required ORM; parameterized queries |
| alembic | Required schema migrations |
| pydantic-settings | Typed configuration from environment variables |
| python-multipart | FastAPI's required parser for file uploads |
| pillow | Image verification, re-encoding, EXIF/GPS stripping |

**Backend dev/CI** (`backend/requirements-dev.txt`): pytest (tests), httpx
(required by FastAPI's TestClient), bandit (static analysis), pip-audit
(vulnerability audit).

**Frontend:** exactly what `create-next-app` installs for TypeScript +
Tailwind (next, react, react-dom, tailwindcss, @tailwindcss/postcss,
typescript, eslint, eslint-config-next, @types/*). No other packages: all
icons, avatars, the logo, and the medals are original inline SVGs.

**Deliberately not added:**
- python-magic: needs a native library; a small magic-byte table covers our allow-list.
- slowapi: IP-keyed by default; a ~40-line per-user limiter fits better.
- An icon library: the icons are original SVGs.

**CI tools** (not app dependencies): actions/checkout, actions/setup-python,
actions/setup-node, and gitleaks/gitleaks-action, all pinned by commit SHA.
Gitleaks-action needs no licence for personal-account repositories; an
organization-owned repo needs a free `GITLEAKS_LICENSE` secret.

## Stubbed, deferred, or incomplete

| Item | Status / seam |
|------|---------------|
| **Authentication** | Stubbed. `X-User-Id` header from the dev account switcher, resolved only in `backend/app/api/deps.py::_identify()`. Refused when `ENVIRONMENT=production`. |
| **Content moderation** | Not built: no reporting, takedown, or admin role. |
| Placeholder videos | Three generated placeholders in `seed-media/`, for you to replace. |
| Video metadata | Videos are validated (container and structure) but not transcoded, so their metadata isn't stripped. Needs ffmpeg. |
| Rate limiter | In-memory, single process. Swap `InMemoryRateLimiter` for a shared store behind the same `RateLimiter` protocol. |
| Object storage | Local disk only. Implement `MediaStorage` (`backend/app/storage/base.py`) for S3/GCS. |
| PostgreSQL | Not tested yet. The schema and queries are portable: set `DATABASE_URL` and install a driver (e.g. psycopg). |
| Ground truth | Stored and hidden, but unused. Seam for a future accuracy-based XP bonus or "reveal". |
| Profile activity | The latest 30 items (max 50), without pagination. The feed is fully cursor-paginated. |
| XP ledger | Not built; `users.xp` is updated atomically. Seam: an `xp_events` audit table. |
| Frontend component tests | Not added (lint + type check only), to keep dependencies minimal. |
| `httpx` → `httpx2` | Starlette now prefers `httpx2` for its TestClient. `httpx` still works; the warning is filtered in `pytest.ini`. Switch after vetting. |
| Dev-only npm advisory | `braces` via `eslint-config-next` has no patched release. Lint-time only; see threat-model gap #9. |
| HTTPS / HSTS | Not applicable locally; required in production. |

See [docs/threat-model.md §5](docs/threat-model.md#5-known-gaps-and-accepted-risks) for the security view of these gaps.
