"""Reclaim expired processing attempts and publish durable queue intents."""

import logging
import time

from app.main import publish_pending_runs, recover_expired_runs

logger = logging.getLogger(__name__)


def main():
    while True:
        try:
            recover_expired_runs()
            publish_pending_runs()
        except Exception:
            logger.exception("Processing reconciliation cycle failed")
        time.sleep(10)


if __name__ == "__main__":
    main()
