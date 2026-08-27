# UpGrade Backend

## Worker (arq)

JIT feed generation runs via `arq` + Redis. Launch the worker with:

```powershell
uv run arq app.workers.feed.WorkerSettings
# or via project script (exposes arq CLI):
uv run worker app.workers.feed.WorkerSettings
```

`app.workers.feed.WorkerSettings` (`backend/app/workers/feed.py:64`) defines:
- `redis_settings` from `REDIS_URL`
- `functions = [generate_feed_batch]`
- `max_tries = 3`, `job_timeout = 120`

Enqueued from `app.services.roadmap._prefetch_first_feed` after roadmap creation; falls back to direct DB generation if Redis is down.
