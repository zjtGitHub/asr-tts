from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
PYTHON = BASE_DIR / ".venv" / "bin" / "python"


def main() -> int:
    python_executable = PYTHON if PYTHON.exists() else Path(sys.executable)
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    process = subprocess.Popen(
        [
            str(python_executable),
            "-m",
            "uvicorn",
            "app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=BASE_DIR,
        env=env,
    )

    def stop(*_args) -> None:
        if process.poll() is None:
            process.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        while process.poll() is None:
            time.sleep(0.25)
    finally:
        stop()
        try:
            return process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
