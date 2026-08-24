"""The public API process: `python -m traffictracker.api`.

Binds to localhost only by default -- a reverse proxy is the only intended
ingress. This process only reads from SQLite storage; it never talks to
the upstream VIC API.
"""

from __future__ import annotations

import logging
import os

import uvicorn

from traffictracker.api.app import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

API_HOST_ENV = "TT_API_HOST"
API_PORT_ENV = "TT_API_PORT"
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000

app = create_app()


def main() -> None:
    host = os.environ.get(API_HOST_ENV) or DEFAULT_API_HOST
    port = int(os.environ.get(API_PORT_ENV) or DEFAULT_API_PORT)
    logger.info("api starting on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
