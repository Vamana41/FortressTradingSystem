## Objectives

* Adopt Python 3.14.0 for local development and services where compatible.

* Maintain OpenAlgo Docker on Python 3.12.x to satisfy 1.0.0.36 minimum.

* Ensure Windows and Linux parity for event loops, networking and SocketIO.

* Raise safety and performance closer to Rust‑level via typing, structured concurrency, bounded resources and observability.

## Compatibility Changes

* Event loop policy:

  1. Windows: set `asyncio.WindowsSelectorEventLoopPolicy()` explicitly in services that previously installed `uvloop`.
  2. Linux/macOS: guarded `uvloop` install; fallback to default `asyncio` when unavailable.

* Flask‑SocketIO workers:

  * Linux containers: keep `eventlet` + Gunicorn; if 3.14 incompatibility appears in any local service, switch to `gevent` worker.

  * Windows dev: use `socketio.run(app)` or Gunicorn equivalent only when supported; fallback to `async_mode='threading'` for local dev if necessary.

* Python selection:

  * `run_system.bat`: prefer `py -3.14`; fallback to `py -3.12` for components with dependency gaps.

  * Validate `pyzmq`, `websockets`, `eventlet/gevent`, `Flask‑SocketIO`, `pydantic/typing` against 3.14 and pin/replace where required.

## 3.14 Safety & Performance Upgrades

* Safety:

  * Enforce `mypy --strict` and `ruff` across custom modules; prefer `dataclasses(frozen=True)` and `typing` to reduce mutable state.

  * Replace shared globals with `contextvars` for request/task scoped data.

  * Input validation for external messages using `pydantic` models.

* Performance & concurrency:

  * Use `asyncio.TaskGroup` for structured parallelism (e.g., margin checks, quotes).

  * Offload blocking broker IO via `asyncio.to_thread` or a bounded `ThreadPoolExecutor`.

  * Add lightweight caches (TTL/LRU) for lot sizes and symbols.

* Memory & longevity:

  * Bounded queues for ZMQ/WS ingestion to prevent unbounded growth; backpressure on producers.

  * Periodic GC/memory watermark logging; cap cache sizes and TTLs; leak detection during soak tests.

* Observability:

  * Structured JSON logging with correlation IDs per signal/order; publish metrics on `events.state.metrics`.

  * Health/heartbeat topics for ZMQ and HTTP endpoints.

## RTD Plugin v3.02.11 Alignment

* Client emits `info` JSON for each active symbol at startup and upon ATM injection; relay passes through without parsing.

* Ensure payload sizes honor relay max (`RELAY_MAX_SIZE`) and document fields used (`an`, `fn`, `cy`, `gc`, etc.).

## File‑Level Updates (Targeted)

* `openalgo/fastapi_main.py`: replace unconditional `uvloop.install()` with OS‑aware loop policy using `asyncio` on Windows and guarded `uvloop` elsewhere.

* `run_system.bat`: interpreter selection to prefer Python 3.14; maintain fallback to 3.12 for any incompatible component.

* Avoid changes to OpenAlgo Dockerfile base (remain 3.12) while validating local 3.14 flows.

## Validation Matrix

* Windows Python 3.14: start Conductor, Strategist, watcher; verify ZMQ topics; exercise REST endpoints; run unit tests under `openalgo/openalgo/test`.

* Windows Python 3.12: rerun if any 3.14 dep fails; confirm fallback.

* Linux/Docker Python 3.12: build and run compose; confirm `5000` and `8765`, SocketIO worker, and websocket proxy.

* Soak tests: 2‑hour run with synthetic signals to check memory stability and latencies.

## Dependency Replacement Rules

* `uvloop` → default `asyncio` on Windows; guarded import on POSIX.

* `eventlet` → `gevent` if needed for 3.14 compatibility; otherwise keep.

* `pyzmq`, `websockets`, `Flask‑SocketIO`, `pydantic` → upgrade to releases declaring 3.14 support; if missing, isolate that service to 3.12.

## Deliverables

* Patches implementing OS‑aware loop policy and interpreter selection.

* Compatibility report across OS and Python versions with any swaps applied (eventlet→gevent, etc.).

* Safety/performance upgrades: structured concurrency, bounded queues/caches, strict typing and lint gates.

* Observability additions: structured logs, health probes, metrics topics.

## Next Steps

* Apply the targeted code updates and launcher adjustments.

* Run the validation matrix; capture outputs and metrics.

* Present results with recommended dependency pins or worker swaps and proceed to integrate RTD `info` messages in the client.
