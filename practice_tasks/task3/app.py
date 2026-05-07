"""
Простое приложение: Flask + Redis + SQLite.
Стратегия: CACHE_STRATEGY = cache_aside | write_through | write_back
"""
from __future__ import annotations

import os
import sqlite3
import threading
from typing import Any

import redis
from flask import Flask, Response, jsonify, request

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.environ.get("SQLITE_PATH", os.path.join(DATA_DIR, "app.db"))
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")
STRATEGY = os.environ.get("CACHE_STRATEGY", "cache_aside").lower()
PORT = int(os.environ.get("PORT", "3000"))
FLUSH_MS = int(os.environ.get("WRITEBACK_FLUSH_MS", "1500"))
CACHE_PREFIX = "item:"
DIRTY_SET = "writeback:dirty_ids"
SEED_COUNT = int(os.environ.get("SEED_COUNT", "1000"))

counter_lock = threading.Lock()
counters: dict[str, int] = {
    "db_reads": 0,
    "db_writes": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "flushes": 0,
    "dirty_peak": 0,
}

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
db_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

app = Flask(__name__)


def _inc(key: str, n: int = 1) -> None:
    with counter_lock:
        counters[key] = counters.get(key, 0) + n


def _snapshot() -> dict[str, Any]:
    with counter_lock:
        h, m = counters["cache_hits"], counters["cache_misses"]
        total = h + m
        hit_rate = (h / total) if total else 0.0
        return {
            "strategy": STRATEGY,
            "dbReads": counters["db_reads"],
            "dbWrites": counters["db_writes"],
            "cacheHits": h,
            "cacheMisses": m,
            "hitRate": hit_rate,
            "flushes": counters["flushes"],
            "dirtyPeak": counters["dirty_peak"],
        }


def _conn_get() -> sqlite3.Connection:
    global _conn
    with db_lock:
        if _conn is None:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
            _conn.commit()
        return _conn


def _db_get_row(item_id: int) -> str | None:
    with db_lock:
        cur = _conn_get().execute("SELECT value FROM items WHERE id = ?", (item_id,))
        row = cur.fetchone()
        _inc("db_reads")
        return row[0] if row else None


def _db_upsert(item_id: int, value: str) -> None:
    with db_lock:
        _conn_get().execute(
            "INSERT INTO items (id, value) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET value = excluded.value",
            (item_id, value),
        )
        _conn_get().commit()
        _inc("db_writes")


def _cache_key(item_id: int) -> str:
    return CACHE_PREFIX + str(item_id)


def _redis_get_through_cache(item_id: int) -> str | None:
    key = _cache_key(item_id)
    cached = r.get(key)
    if cached is not None:
        _inc("cache_hits")
        return cached
    _inc("cache_misses")
    val = _db_get_row(item_id)
    if val is None:
        return None
    r.set(key, val)
    return val


def _put_cache_aside(item_id: int, value: str) -> None:
    _db_upsert(item_id, value)
    r.delete(_cache_key(item_id))


def _put_write_through(item_id: int, value: str) -> None:
    _db_upsert(item_id, value)
    r.set(_cache_key(item_id), value)


def _track_dirty_peak() -> None:
    n = int(r.scard(DIRTY_SET))
    with counter_lock:
        if n > counters["dirty_peak"]:
            counters["dirty_peak"] = n


def _put_write_back(item_id: int, value: str) -> None:
    r.set(_cache_key(item_id), value)
    r.sadd(DIRTY_SET, str(item_id))
    _track_dirty_peak()


def _flush_write_back() -> None:
    ids = list(r.smembers(DIRTY_SET))
    if not ids:
        return
    for sid in ids:
        key = CACHE_PREFIX + sid
        val = r.get(key)
        if val is None:
            r.srem(DIRTY_SET, sid)
            continue
        _db_upsert(int(sid), val)
        r.srem(DIRTY_SET, sid)
    _inc("flushes")


def _get_item(item_id: int) -> str | None:
    if STRATEGY == "cache_aside":
        return _redis_get_through_cache(item_id)
    if STRATEGY == "write_through":
        return _redis_get_through_cache(item_id)
    if STRATEGY == "write_back":
        return _redis_get_through_cache(item_id)
    raise RuntimeError(f"Unknown CACHE_STRATEGY={STRATEGY}")


def _put_item(item_id: int, value: str) -> None:
    if STRATEGY == "cache_aside":
        _put_cache_aside(item_id, value)
    elif STRATEGY == "write_through":
        _put_write_through(item_id, value)
    elif STRATEGY == "write_back":
        _put_write_back(item_id, value)
    else:
        raise RuntimeError(f"Unknown CACHE_STRATEGY={STRATEGY}")


def _reset_counters() -> None:
    with counter_lock:
        for k in counters:
            counters[k] = 0


def _reseed_db() -> None:
    with db_lock:
        c = _conn_get()
        c.execute("DELETE FROM items")
        c.executemany(
            "INSERT INTO items (id, value) VALUES (?, ?)",
            [(i, f"seed-{i}") for i in range(1, SEED_COUNT + 1)],
        )
        c.commit()


_stop_flush = threading.Event()
_flush_thread: threading.Thread | None = None
_shutdown_lock = threading.Lock()
_shutdown_ran = False


def _flush_loop() -> None:
    while True:
        if _stop_flush.wait(FLUSH_MS / 1000.0):
            return
        try:
            _flush_write_back()
        except Exception as e:  # noqa: BLE001
            print("flush error:", e)


@app.get("/health")
def health() -> Any:
    return jsonify(ok=True, strategy=STRATEGY)


@app.get("/metrics")
def metrics() -> Any:
    return jsonify(_snapshot())


@app.post("/admin/reset-metrics")
def admin_reset_metrics() -> Any:
    _reset_counters()
    return jsonify(ok=True)


@app.post("/admin/isolate-test")
def admin_isolate() -> Any:
    _reset_counters()
    r.flushdb()
    _reseed_db()
    return jsonify(ok=True, seeded=SEED_COUNT)


@app.get("/item/<int:item_id>")
def get_item(item_id: int) -> Any:
    v = _get_item(item_id)
    if v is None:
        return jsonify(error="not found"), 404
    return Response(v, mimetype="text/plain")


@app.put("/item/<int:item_id>")
def put_item(item_id: int) -> Any:
    body = request.get_json(silent=True) or {}
    value = body.get("value")
    if not isinstance(value, str):
        return jsonify(error="value string required"), 400
    _put_item(item_id, value)
    return jsonify(ok=True)


def _shutdown() -> None:
    global _shutdown_ran
    with _shutdown_lock:
        if _shutdown_ran:
            return
        _shutdown_ran = True
    _stop_flush.set()
    if STRATEGY == "write_back":
        try:
            _flush_write_back()
        except Exception as e:  # noqa: BLE001
            print("final flush:", e)
    try:
        r.close()
    except Exception:
        pass
    with db_lock:
        global _conn
        if _conn:
            _conn.close()
            _conn = None


def main() -> None:
    if os.environ.get("FLUSH_REDIS_ON_START", "1") != "0":
        r.flushdb()
        print("redis: flushdb on start (FLUSH_REDIS_ON_START=0 to skip)")

    global _flush_thread
    if STRATEGY == "write_back":
        _flush_thread = threading.Thread(target=_flush_loop, daemon=True)
        _flush_thread.start()

    print(f"app strategy={STRATEGY} port={PORT}")
    try:
        from waitress import serve
        serve(app, host="127.0.0.1", port=PORT, threads=16, _quiet=True)
    finally:
        _shutdown()


if __name__ == "__main__":
    main()
