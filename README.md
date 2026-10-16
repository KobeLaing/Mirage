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
  app/scanner/   AI Authenticity Scanner: detector interface, registry, detectors, weights
frontend/    Next.js 16 (App Router) + TypeScript + Tailwind
seed-media/  images used by the seed script (the MP4s are test fixtures only)
docs/        requirements, design, threat model
```

## Features

- **Sign-in**: username and password, Argon2id hashes, a signed httpOnly
  session cookie, CSRF protection, login rate limits, and a honeypot field
  for bots. Every page except `/login` requires a signed-in user.
- **Feed and profiles**: post images or videos, vote AI/Real (+10 XP), post
  (+20 XP), react, and **comment** (no XP).
- **Left side pane** on the feed and profile pages:
  1. **Leaderboard**: top 50 by XP, with your row highlighted.
  2. **Blind Mode**: hides vote counts, results and comments until you vote.
     Enforced by the API, not just hidden in the browser.
  3. **AI Authenticity Scanner**: privately check an image or video for signs
     of AI generation. Runs locally; the file is deleted after the scan.

## Prerequisites

- **Python 3.12+**
- **Node.js 24 LTS**

## Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt # or requirements.txt for runtime only
copy .env.example .env              # then fill in the secrets (below)
python -m scripts.seed              # 6 demo users, 7 demo posts, demo votes (safe to re-run)
python run.py                       # migrates, then serves on http://localhost:8000
```

**Secrets in `backend/.env`** (gitignored; never commit it):

| Variable | What it is |
|----------|------------|
| `SESSION_SECRET` | Signs session cookies. **Required**: the API won't start without it. At least 32 characters: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `SEED_KOBE_PASSWORD`, `SEED_KARA_PASSWORD`, `SEED_ALTAIR_PASSWORD`, `SEED_JOSIE_PASSWORD`, `SEED_TERRA_PASSWORD`, `SEED_RIVER_PASSWORD` | Passwords for the seeded accounts. Only the seed script reads them, and only their Argon2 hashes are stored. |

- `python run.py --reload` auto-reloads on code changes.
- Health check: <http://localhost:8000/health>
- API docs (development only): <http://localhost:8000/docs>
- Data lives in `backend/var/` (SQLite DB and uploads). Delete it and re-seed to start fresh.

## Frontend

```powershell
cd frontend
npm ci
copy .env.example .env.local        # optional: points at http://localhost:8000
npm run dev                         # http://localhost:3000
```

Open <http://localhost:3000> and sign in. Use `localhost` for both the API
and the site, not `127.0.0.1` for one of them: the session cookie belongs to
a host name, and the two count as different hosts.

### Seeded accounts

Passwords are whatever you put in `backend/.env`.

| Username | Name | Rank | Posted |
|----------|------|------|--------|
| `KobeLaing` | Kobe Laing | Silver, 150 XP | 2 images |
| `KaraMercer` | Kara Mercer | Gold, 600 XP | 1 image |
| `AltairVance` | Altair Vance | Bronze | AIoasis.jpg (AI: 3 AI votes, 1 Real) |
| `JosieHart` | Josie Hart | Bronze | bluehummingbird.jpg (AI: 2 AI votes, 1 Real) |
| `TerraOkafor` | Terra Okafor | Bronze | realpainting3.jpg (Real: 3 Real votes) |
| `RiverCalloway` | River Calloway | Bronze | realpainting4.jpg (Real: 3 Real votes) |

## AI Authenticity Scanner

Upload an image or video in the side pane. It is validated exactly like a
post upload (type from the file's bytes, size limits), analysed on this
machine, and deleted when the scan finishes. It is never posted or stored.

The result is an AI probability from 0 to 100%, a breakdown per signal, and
this notice: *"This score is an estimate, not proof. Detectors can be wrong,
especially on compressed or edited media."* When no signal is strong enough,
the result says **Inconclusive** and shows no number.

| Detector | Media | How it works | Library |
|----------|-------|--------------|---------|
| Content Credentials | image, video | Reads the signed C2PA manifest; an AI "digital source type" is decisive | `c2pa-python` |
| File metadata | image | EXIF camera data, editing software, generator names/settings in EXIF, XMP and PNG text | Pillow |
| Frequency analysis (FFT) | image | Isolated peaks in the 2-D spectrum = repeating upsampling grid | NumPy, OpenCV |
| Noise residual | image | Sensor-like grain that grows with brightness vs. unnaturally clean areas | NumPy, OpenCV |
| Error Level Analysis | image (JPEG) | Re-save at a known quality; areas that change differently suggest editing | Pillow, NumPy |
| Frame sampling | video | FFT + noise on frames sampled evenly through the clip, combined by median | OpenCV, NumPy |
| Temporal consistency | video | Farneback optical flow; change that motion can't explain = flicker/morphing | OpenCV |
| Container metadata | video | MP4 encoder tag (©too), phone camera tags, generator names | standard library |
| Face-swap detection | video | YuNet face finder + your ONNX face-swap classifier. **Off by default** | OpenCV DNN |

Weights, on/off flags and thresholds live in
[`backend/app/scanner/scanner.toml`](backend/app/scanner/scanner.toml); the
weighting is explained in
[`backend/app/scanner/combine.py`](backend/app/scanner/combine.py).

### Enabling face-swap detection

No face-swap model ships with Mirage (none we found is both maintained and
clearly licensed to redistribute). To use one:

1. `python -m scripts.fetch_models` downloads the YuNet face finder into
   `backend/models/` and checks its SHA-256.
2. Put an ONNX face-swap classifier somewhere on disk and set
   `DEEPFAKE_MODEL_PATH` in `backend/.env`.
3. In `scanner.toml`, set `[detectors.face_swap] enabled = true` and match
   `input_size`, `mean`, `std`, `fake_index` and `activation` to your model.

### Adding a new detector

Every detector is one module behind the same interface
(`backend/app/scanner/base.py`), so adding one never touches the scanner
service. For example, to add a Hugging Face classifier or a Hive API check:

1. **Create the module**: `backend/app/scanner/detectors/my_detector.py`
   with a class extending `Detector`:
   ```python
   class MyDetector(Detector):
       name = "my_detector"              # also its section name in scanner.toml
       label = "My detector"             # shown on the results screen
       media_types = frozenset({"image"})
       # For anything that uploads media elsewhere (Hive, Sightengine,
       # Reality Defender, Hugging Face Inference API):
       sends_media_off_device = True
       api_key_env = "MYSERVICE_API_KEY"

       def unavailable_reason(self):     # optional: missing model or library
           return None

       def analyze(self, media: MediaInput) -> DetectorResult:
           api_key = os.environ[self.api_key_env]
           ...  # read media.path / media.rgb, call your model or API
           return DetectorResult(score=0.8, confidence=0.7, conclusive=True,
                                 explanation="One plain-English sentence.")
   ```
   `score` is 0 (real) to 1 (AI), or `None` if there's nothing to judge.
   Raising an exception is safe: the scan reports this detector as failed
   and carries on.
2. **Register it**: add the class to `DETECTOR_CLASSES` in
   `backend/app/scanner/registry.py`.
3. **Configure it**: add a table to `scanner.toml`:
   ```toml
   [detectors.my_detector]
   enabled = true
   weight = 2.0
   ```
4. **API key** (off-device detectors only): add `MYSERVICE_API_KEY=` to
   `backend/.env.example`, and the real key to `backend/.env`. A detector with
   `sends_media_off_device = True` is skipped, and nothing leaves the
   machine, unless it is explicitly enabled **and** its key is set.
5. **Dependencies and tests**: pin any new package in `requirements.txt`, and
   add tests next to `backend/tests/test_scanner.py`. For an API detector,
   mock the HTTP call; tests must not reach the network.
6. **Threat model**: an off-device detector sends user files to a third
   party. Note that in `docs/threat-model.md` and in the UI copy before
   enabling it.

## Tests and security checks

The same checks run in CI (`.github/workflows/ci.yml`) on every push and pull request.

| Check | Command (from `backend/` or `frontend/`) |
|-------|------------------------------------------|
| Backend tests (261) | `python -m pytest` |
| Python static analysis | `python -m bandit -c pyproject.toml -r app scripts run.py` |
| Python dependency audit | `python -m pip_audit -r requirements.txt -r requirements-dev.txt --strict` |
| Frontend lint | `npm run lint` |
| Frontend type check | `npm run typecheck` |
| npm dependency audit | `npm audit --omit=dev --audit-level=high` |
| Secret scan | CI (Gitleaks). Locally: `gitleaks git .` |

## Dependencies and why each is there

**Backend runtime** (`backend/requirements.txt`, fully pinned)

| Package | Why |
|---------|-----|
| fastapi | Web framework (brings pydantic and starlette) |
| uvicorn | ASGI server |
| SQLAlchemy | ORM; parameterized queries |
| alembic | Schema migrations |
| pydantic-settings | Typed configuration from environment variables |
| python-multipart | FastAPI's parser for file uploads |
| pillow | Image verification, re-encoding, EXIF stripping; scanner metadata and ELA |
| argon2-cffi | Argon2id password hashing |
| itsdangerous | Signed, timestamped session cookies |
| numpy | Scanner pixel statistics |
| opencv-python-headless | Scanner video decoding, optical flow, face finding |
| c2pa-python | Reading and verifying C2PA Content Credentials |

**Backend dev/CI** (`backend/requirements-dev.txt`): pytest, httpx (FastAPI's
TestClient), bandit, pip-audit.

**Frontend:** exactly what `create-next-app` installs for TypeScript +
Tailwind. No other packages: icons, avatars, logo and medals are original
inline SVGs.

## Stubbed, deferred, or incomplete

| Item | Status / seam |
|------|---------------|
| **Face-swap model** | Detector built but off by default; no model ships. See "Enabling face-swap detection". |
| Scanner accuracy | The pixel detectors (FFT, noise, ELA, temporal) are heuristics with deliberately low weight; they can't produce a verdict alone. Only C2PA and metadata are strong. |
| Account management | No sign-up, password change or reset. Accounts come from the seed script. |
| Content moderation | Not built: no reporting, takedown, or admin role. |
| Video metadata | Posted videos are validated but not transcoded, so their metadata isn't stripped. |
| Rate limiter | In-memory, single process. Swap `InMemoryRateLimiter` for a shared store (e.g. Redis). Login limits reset on restart. |
| Reverse proxy | Login rate limiting uses the direct client IP. Behind a proxy, read its forwarded header (see `deps.client_ip`). |
| Media URLs | `/api/v1/media/{key}` is served without a session (random 128-bit keys), so image tags work everywhere. |
| Object storage | Local disk only. Implement `MediaStorage` for S3/GCS. |
| PostgreSQL | Not tested yet; the schema and queries are portable. |
| Frontend component tests | Not added (lint + type check only). Honeypot and Blind Mode are tested at the API. |
| `httpx` → `httpx2` | Starlette prefers `httpx2` for its TestClient; the warning is filtered in `pytest.ini`. |
| HTTPS / HSTS | Not applicable locally; required in production. |

See [docs/threat-model.md](docs/threat-model.md) for the security view of these gaps.
