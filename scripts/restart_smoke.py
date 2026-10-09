"""Ручной smoke перезапуска: кейс обязан пережить перезапуск процесса.

Запуск:
    python scripts/restart_smoke.py

Скрипт поднимает uvicorn в отдельном процессе, создаёт кейс, убивает сервер,
поднимает новый на том же DATABASE_PATH и читает кейс обратно.
Автотест tests/test_sandbox_cases.py::TestRestartAcrossProcesses делает то же самое,
но без запуска реального сетевого сервера; этот скрипт нужен для демонстрации вживую.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.getenv("SMOKE_PORT", "8123"))
BASE = f"http://127.0.0.1:{PORT}"
ALICE = "smoke-alice"
BOB = "smoke-bob"
KEY = "smoke-shared-key"


class HeaderGetter:
    """HTTP-заголовки регистронезависимы, но не все клиенты это учитывают."""

    def __init__(self, headers: dict) -> None:
        self._headers = {k.lower(): v for k, v in headers.items()}

    def get(self, name: str, default=None):
        return self._headers.get(name.lower(), default)


def post_case(evaluation_id: str, subject: str) -> tuple[int, dict, HeaderGetter]:
    body = json.dumps({
        "evaluation_id": evaluation_id,
        "selected_language": "ru",
        "contact_reason": "suspicious_transfer_request",
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/sandbox/cases", data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Sandbox-Subject": subject,
            "Idempotency-Key": KEY,
        })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read()), HeaderGetter(dict(resp.headers))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}"), HeaderGetter(dict(exc.headers))


def get_case(case_id: str, subject: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"{BASE}/sandbox/cases/{case_id}",
                                 headers={"X-Sandbox-Subject": subject})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def get_json(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as resp:
        return json.loads(resp.read())


def start_server(db_path: Path) -> subprocess.Popen:
    env = dict(os.environ)
    env["DATABASE_PATH"] = str(db_path)
    # Скрипт проверяет SQLite-рестарт: гасим PG_DSN из .env/.env.example,
    # иначе сервер уйдёт в PostgreSQL и тест будет не о том.
    env["PG_DSN"] = ""
    env["LOG_LEVEL"] = os.getenv("LOG_LEVEL", "INFO")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--log-level", "warning"],
        cwd=REPO_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    for _ in range(60):
        time.sleep(0.25)
        try:
            get_json("/api/health")
            return proc
        except Exception:
            if proc.poll() is not None:
                raise RuntimeError("сервер не поднялся")
    raise RuntimeError("сервер не ответил за 15 секунд")


def stop_server(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, check=False)
    else:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    proc.wait(timeout=15)


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {label}{(' :: ' + detail) if detail else ''}")
    return ok


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "restart_smoke.db"

        print("== фаза 1: первый запуск ==")
        server = start_server(db_path)
        try:
            status, case, headers = post_case("eval-alice-1", ALICE)
            failures += not check("alice создаёт кейс", status == 201, f"status={status}")
            case_id = case.get("case_id", "")
            failures += not check("case_id выдан", case_id.startswith("case_"), case_id)
            failures += not check("Idempotency-Replayed=false",
                                  headers.get("Idempotency-Replayed") == "false")

            status, replay, headers = post_case("eval-alice-1", ALICE)
            failures += not check("alice replay -> 200 и тот же case_id",
                                  status == 200 and replay.get("case_id") == case_id,
                                  f"status={status}")
            failures += not check("Idempotency-Replayed=true",
                                  headers.get("Idempotency-Replayed") == "true")

            status, bob, _ = post_case("eval-alice-1", BOB)
            failures += not check("bob с тем же ключом -> 201 и свой кейс",
                                  status == 201 and bob.get("subject_ref") == BOB
                                  and bob.get("case_id") != case_id, f"status={status}")

            status, _ = get_case(case_id, BOB)
            failures += not check("bob не видит кейс alice", status == 404, f"status={status}")
        finally:
            stop_server(server)

        print("\n== фаза 2: перезапуск на том же DATABASE_PATH ==")
        server = start_server(db_path)
        try:
            status, fetched = get_case(case_id, ALICE)
            failures += not check("кейс alice пережил перезапуск", status == 200, f"status={status}")
            failures += not check("case_id не изменился", fetched.get("case_id") == case_id)
            failures += not check("status остался created", fetched.get("status") == "created")
            failures += not check("песочница помечена sandbox", fetched.get("sandbox") is True)
            print(f"      created_at={fetched.get('created_at')}")
        finally:
            stop_server(server)

    print("\n== итог ==")
    if failures:
        print(f"ПРОВАЛЕНО проверок: {failures}")
        return 1
    print("все проверки пройдены")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())