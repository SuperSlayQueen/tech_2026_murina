#!/usr/bin/env python3
"""Запуск матрицы: 3 стратегии × 3 профиля. Нужны Redis и зависимости (pip install -r requirements.txt)."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
DB_FILES = ("app.db", "app.db-wal", "app.db-shm")
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:3000")
DURATION = os.environ.get("TEST_DURATION_SEC", "5")
CONCURRENCY = os.environ.get("TEST_CONCURRENCY", "15")

STRATEGIES = ("cache_aside", "write_through", "write_back")
PROFILES = (
    ("read-heavy", "0.8"),
    ("balanced", "0.5"),
    ("write-heavy", "0.2"),
)


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=kw.get("cwd", ROOT))


def wipe_db() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    for name in DB_FILES:
        path = os.path.join(DATA_DIR, name)
        if os.path.isfile(path):
            os.remove(path)


def wait_health() -> None:
    url = BASE_URL.rstrip("/") + "/health"
    for _ in range(120):
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise RuntimeError("health check timeout")


def wait_port_free(host: str, port: int, attempts: int = 60) -> None:
    import socket
    for _ in range(attempts):
        s = socket.socket()
        try:
            s.settimeout(0.3)
            s.connect((host, port))
            s.close()
            time.sleep(1.0)
        except OSError:
            return
    raise RuntimeError(f"port {port} not freed")


def post(path: str) -> None:
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + path,
        data=b"",
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status not in (200, 204):
            raise RuntimeError(path)


def main() -> None:
    print("Перед запуском: Redis (docker compose up -d в каталоге task3).")
    print("Установка: pip install -r requirements.txt\n")

    run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])

    for strat in STRATEGIES:
        print("\n########## STRATEGY", strat, "##########\n")
        wipe_db()
        run([sys.executable, "seed.py"])

        env = os.environ.copy()
        env["CACHE_STRATEGY"] = strat
        env["PORT"] = "3000"
        proc = subprocess.Popen(
            [sys.executable, "app.py"],
            env=env,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wait_health()
            for name, ratio in PROFILES:
                post("/admin/isolate-test")
                print(f"\n--- {strat} / {name} ---\n")
                run(
                    [
                        sys.executable,
                        "loadgen.py",
                        "--base-url",
                        BASE_URL,
                        "--duration-sec",
                        DURATION,
                        "--concurrency",
                        CONCURRENCY,
                        "--read-ratio",
                        ratio,
                        "--label",
                        f"{strat}:{name}",
                    ]
                )
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            wait_port_free("127.0.0.1", 3000)

    print("\nГотово. Сохраните вывод терминала для отчёта (скриншоты).")


if __name__ == "__main__":
    main()
