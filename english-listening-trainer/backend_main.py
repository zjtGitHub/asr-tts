from __future__ import annotations

import os

import uvicorn

from app import app


def main() -> None:
    host = os.getenv("ELT_BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("ELT_BACKEND_PORT", "8000"))

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
        loop="asyncio",
        http="h11",
        ws="none",
    )


if __name__ == "__main__":
    main()
