# UpGrade — AI-Powered Learning App

Monorepo for **UpGrade** — personal AI-powered learning platform for anyone who is learning stuff.

> Stack (Aug 2026 — latest stable verified):
> - **Frontend:** Flutter **3.47.1** • Dart **3.13.1** • Material 3 (empty template) — `mobile/`
> - **Backend:** FastAPI **0.141.1** • Pydantic **2.13.4** • Python **3.13** via **uv 0.12.5** — `backend/`

Initialized 2026-08-24 — no features yet, only project scaffolding.

---

## Structure

```
UpGrade/
├── mobile/              # Flutter app — com.upgrade / upgrade
│   ├── lib/
│   │   ├── main.dart                # Hello World! (empty template)
│   │   ├── app/         # composition root — router, theme, app.dart
│   │   ├── core/        # shared kernel — config, theme, widgets, utils
│   │   │   ├── config/app_config.dart
│   │   │   └── theme/app_theme.dart
│   │   ├── features/    # vertical slices — data/domain/presentation
│   │   │   └── learning/{data,domain,presentation}
│   │   └── l10n/        # localizations (gen-l10n, in-source)
│   ├── android/ ios/ web/ windows/ macos/ linux/
│   ├── pubspec.yaml     # sdk: ^3.13.1, flutter_lints ^6.0.0
│   └── analysis_options.yaml
│
├── backend/             # FastAPI app — uv flat layout (no src/)
│   ├── app/
│   │   ├── main.py              # lifespan + CORSMiddleware + / + /health
│   │   ├── core/config.py       # BaseSettings (pydantic-settings)
│   │   ├── api/routers/health.py
│   │   ├── db/database.py       # Postgres / Neon wiring
│   │   ├── db/redis.py          # Redis client & health checks (redis.asyncio)
│   │   ├── models/ schemas/ services/
│   │   ├── tools/               # LLM tool schemas & execution boundary
│   │   ├── workers/             # arq background task workers
│   │   └── api/deps.py
│   ├── tests/test_health.py, test_redis.py
│   ├── pyproject.toml   # requires-python >=3.13, ruff, mypy, pytest
│   ├── uv.lock
│   ├── .python-version  # 3.13
│   └── .env.example
│
├── .github/workflows/ci.yml     # GitHub Actions CI for backend and mobile
└── README.md
```

---

## Prerequisites

- **Flutter:** `C:\Users\bari2\dev\flutter` added to User PATH. Verify: `flutter --version` → 3.47.1 / Dart 3.13.1. JDK 17+, Android SDK if building APK.
- **Backend:** `uv` 0.12.5 + Python 3.13.14 (`py -3.13`). No manual venv — `uv` manages `.venv` + `uv.lock`.
- **Editor:** VS Code + Flutter/Dart + Python extensions.

---

## Quick Start

### Backend

```powershell
cd C:\Users\bari2\Desktop\UpGrade\backend

# install (creates .venv)
uv sync

# dev with auto-reload (docs at http://127.0.0.1:8000/docs)
uv run fastapi dev app/main.py
# or
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# prod
uv run fastapi run app/main.py
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# quality
uv run ruff check . --fix; uv run ruff format .
uv run mypy app
uv run pytest -v
```

Health check: `GET /health` → `{"status":"ok"}`. Root: `GET /` → `{"message":"Welcome to UpGrade API","env":"development"}`

Env: copy `.env.example` → `.env`, edit `pydantic-settings` values in `app/core/config.py`.

### Mobile (Flutter)

```powershell
cd C:\Users\bari2\Desktop\UpGrade\mobile

flutter pub get
flutter analyze        # No issues found!
flutter test
flutter run            # pick device; or flutter run -d windows / -d chrome
flutter build apk      # android
flutter build windows
```

The app currently shows `Hello World!` (empty template). Clean-architecture folders are ready for `flutter_riverpod` / `riverpod_generator` / `go_router` / `dio` when you start features.

---

## 2026 Notes (what was verified at init)

- Flutter 3.47.1 requires `minSdkVersion 24`, Gradle 8.7, AGP 8.6, Java 17; Impeller now default on desktop; `flutter_localizations` unbundled.
- FastAPI `app.on_event` is deprecated since 0.93 — this project uses `lifespan` (`asynccontextmanager`). CORS via `CORSMiddleware`; env via `pydantic-settings` `SettingsConfigDict(env_file=".env")`.
- `uv` is the standard package manager — `pip/poetry` not used. Lockfile `uv.lock` is committed; CI uses `uv sync --frozen`.

---

## Provisioning & Infrastructure

### 1. Neon Postgres
- **Database URL:** Configured in `backend/.env` via `DATABASE_URL`.
- **Neon Console:** Create project / branch on [neon.tech](https://neon.tech), grab connection string (`postgresql://neondb_owner:...@ep-...aws.neon.tech/neondb?sslmode=require`).
- **Connection Wiring:** Managed in `app/db/database.py` and `app/core/config.py`.

### 2. Redis
- **Redis URL:** Configured in `backend/.env` via `REDIS_URL` (default: `redis://localhost:6379/0` for local, or Upstash / Managed Redis URL for cloud).
- **Used for:** arq background task queue (JIT feed generation), JWT refresh token revocation store, and Open Chat rate limiting (50 msg/hr).
- **Async Client:** Managed via `app/db/redis.py` (`redis.asyncio` with connection pooling, health checks, and lifespan teardown).

### 3. Continuous Integration (CI)
- `.github/workflows/ci.yml` runs on push and PR to `main`.
- **Backend:** `uv sync --frozen`, `ruff check .`, `ruff format --check .`, `mypy app`, `pytest -v`.
- **Mobile:** `flutter analyze`.

---

## Next Steps (when you start features)

1. **Auth:** better-auth / JWT in `backend/app/api/routers/auth.py` + `mobile/lib/features/auth/`
2. **AI learning:** OpenAI / Workers AI client in `backend/app/services/ai.py`, streaming endpoints
3. **State:** `flutter pub add flutter_riverpod riverpod_annotation go_router dio json_serializable build_runner`
4. **DB:** SQLModel 0.0.39 + asyncpg + alembic (`alembic` dir placeholder exists)

---

## License

Private — not published.
