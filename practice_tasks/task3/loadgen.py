"""Простой генератор нагрузки. Пример:
python loadgen.py --base-url http://127.0.0.1:3000 --duration-sec 5 --concurrency 15 --read-ratio 0.8
"""
from __future__ import annotations

import argparse
import random
import threading
import time

import requests
from requests.adapters import HTTPAdapter


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:3000")
    p.add_argument("--duration-sec", type=float, default=15.0)
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--read-ratio", type=float, default=0.8)
    p.add_argument("--max-id", type=int, default=1000)
    p.add_argument("--label", default="")
    return p.parse_args()


def make_session(pool: int) -> requests.Session:
    s = requests.Session()
    adapter = HTTPAdapter(pool_connections=pool, pool_maxsize=pool, max_retries=0)
    s.mount("http://", adapter)
    return s


def worker(session: requests.Session, base: str, end: float, read_ratio: float, max_id: int,
           latencies: list[float], errors: list[int]) -> None:
    while time.time() < end:
        iid = random.randint(1, max_id)
        t0 = time.perf_counter()
        try:
            if random.random() < read_ratio:
                resp = session.get(f"{base}/item/{iid}", timeout=10)
                ok = resp.status_code in (200, 404)
            else:
                payload = {"value": f"w-{time.time()}-{random.random()}"}
                resp = session.put(f"{base}/item/{iid}", json=payload, timeout=10)
                ok = resp.status_code == 200
            ms = (time.perf_counter() - t0) * 1000
            (latencies if ok else errors).append(ms if ok else 0)
        except Exception:
            errors.append(0)


def main() -> None:
    a = parse_args()
    base = a.base_url.rstrip("/")
    label = a.label or f"read_ratio={a.read_ratio}"
    print("=== load-generator ===")
    print(
        {
            "baseUrl": base,
            "durationSec": a.duration_sec,
            "concurrency": a.concurrency,
            "readRatio": a.read_ratio,
            "maxId": a.max_id,
            "label": label,
        }
    )

    session = make_session(a.concurrency)
    try:
        session.post(f"{base}/admin/reset-metrics", timeout=10)
    except Exception:
        pass

    latencies: list[float] = []
    errors: list[int] = []
    lock = threading.Lock()
    end = time.time() + a.duration_sec

    def wrap() -> None:
        loc_lat: list[float] = []
        loc_err: list[int] = []
        worker(session, base, end, a.read_ratio, a.max_id, loc_lat, loc_err)
        with lock:
            latencies.extend(loc_lat)
            errors.extend(loc_err)

    t0 = time.time()
    threads = [threading.Thread(target=wrap) for _ in range(a.concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - t0

    ok = len(latencies)
    fail = len(errors)
    thr = ok / elapsed if elapsed > 0 else 0
    avg = sum(latencies) / len(latencies) if latencies else 0
    try:
        srv = session.get(f"{base}/metrics", timeout=10).json()
    except Exception:
        srv = None

    print("--- results ---")
    print("label:", label)
    print("elapsedSec:", round(elapsed, 2))
    print("completedRequests:", ok + fail)
    print("failedRequests:", fail)
    print("throughput_req_per_sec:", round(thr, 2))
    print("avg_latency_ms:", round(avg, 3))
    if srv:
        print("server_dbReads:", srv.get("dbReads"))
        print("server_dbWrites:", srv.get("dbWrites"))
        print("server_cacheHits:", srv.get("cacheHits"))
        print("server_cacheMisses:", srv.get("cacheMisses"))
        print("server_hitRate:", round(srv.get("hitRate", 0), 4))
        print("server_flushes:", srv.get("flushes"))
        print("server_dirtyPeak:", srv.get("dirtyPeak"))


if __name__ == "__main__":
    main()
