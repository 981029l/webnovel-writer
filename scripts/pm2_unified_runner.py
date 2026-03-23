#!/usr/bin/env python3
"""Single-process supervisor for PM2 that launches both backend and frontend."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_PORT = os.environ.get("BACKEND_PORT", "8080")
FRONTEND_PORT = os.environ.get("FRONTEND_PORT", "5173")


processes: dict[str, subprocess.Popen[str]] = {}
shutdown_requested = False


def stream_output(name: str, pipe) -> None:
    try:
        for line in iter(pipe.readline, ""):
            if not line:
                break
            print(f"[{name}] {line.rstrip()}", flush=True)
    finally:
        pipe.close()


def start_process(name: str, command: list[str], cwd: Path) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
        env=os.environ.copy(),
    )
    processes[name] = process

    thread = threading.Thread(
        target=stream_output,
        args=(name, process.stdout),
        daemon=True,
    )
    thread.start()
    return process


def terminate_process(name: str, process: subprocess.Popen[str], sig: int) -> None:
    if process.poll() is not None:
        return

    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        return


def stop_all(sig: int = signal.SIGTERM) -> None:
    for name, process in list(processes.items()):
        terminate_process(name, process, sig)

    deadline = time.time() + 10
    for process in list(processes.values()):
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            pass

    for name, process in list(processes.items()):
        if process.poll() is None:
            print(f"[supervisor] force killing {name}", flush=True)
            terminate_process(name, process, signal.SIGKILL)
            process.wait()


def handle_signal(signum: int, _frame) -> None:
    global shutdown_requested
    if shutdown_requested:
        return

    shutdown_requested = True
    print(f"[supervisor] received signal {signum}, stopping services", flush=True)
    stop_all()
    sys.exit(0)


def main() -> int:
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    print("[supervisor] starting backend and frontend", flush=True)

    start_process(
        "backend",
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            BACKEND_PORT,
        ],
        BACKEND_DIR,
    )
    start_process(
        "frontend",
        [
            "npm",
            "run",
            "dev",
            "--",
            "--host",
            "0.0.0.0",
            "--port",
            FRONTEND_PORT,
        ],
        FRONTEND_DIR,
    )

    while True:
        for name, process in list(processes.items()):
            return_code = process.poll()
            if return_code is None:
                continue

            if shutdown_requested:
                return 0

            print(
                f"[supervisor] {name} exited with code {return_code}, stopping remaining services",
                flush=True,
            )
            stop_all()
            return return_code or 1

        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
