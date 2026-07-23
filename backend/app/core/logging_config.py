"""Logging setup for the FastAPI process."""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once for app + uvicorn-friendly consistency."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(numeric)
        for handler in root.handlers:
            handler.setLevel(numeric)
        return

    logging.basicConfig(
        level=numeric,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
