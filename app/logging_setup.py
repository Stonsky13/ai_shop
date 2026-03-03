from __future__ import annotations

import logging
import sys


def setup_logging(level: str) -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(lvl)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(lvl)
