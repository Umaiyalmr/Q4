
import json
import time
import uuid
from collections import deque
from threading import Lock
from datetime import datetime, timezone

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse

app = FastAPI(title="Production Observability API")

EMAIL = "23f2005531@ds.study.iitm.ac.in"
START_TIME = time.monotonic()

# Prometheus counter
http_requests_total = 0
counter_lock = Lock()

# Store recent structured request logs
MAX_LOG_ENTRIES = 1000
request_logs = deque(maxlen=MAX_LOG_ENTRIES)
logs_lock = Lock()


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    global http_requests_total

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = time.perf_counter()

    # Increment for every incoming HTTP request, including health and metrics.
    with counter_lock:
        http_requests_total += 1

    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    elapsed = time.perf_counter() - start

    entry = {
        "level": "info" if response.status_code < 500 else "error",
        "ts": datetime.now(timezone.utc).isoformat(),
        "path": request.url.path,
        "request_id": request_id,
    }

    with logs_lock:
        request_logs.append(entry)

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/work")
async def work(n: int = Query(default=1, ge=0)):
    # Perform n units of simple work.
    result = sum(range(n + 1))

    return {
        "email": EMAIL,
        "done": n,
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    with counter_lock:
        current_count = http_requests_total

    # Prometheus text exposition format.
    return (
        "# HELP http_requests_total Total number of HTTP requests.\n"
        "# TYPE http_requests_total counter\n"
        f"http_requests_total {current_count}\n"
    )


@app.get("/healthz")
async def healthz():
    uptime = max(0.0, time.monotonic() - START_TIME)

    return {
        "status": "ok",
        "uptime_s": uptime,
    }


@app.get("/logs/tail")
async def logs_tail(limit: int = Query(default=10, ge=0)):
    with logs_lock:
        entries = list(request_logs)[-limit:] if limit else []

    return entries


# CORS: allow browser-based grader access.
# Keep this as the only CORS configuration.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
