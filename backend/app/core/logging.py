"""Application logging configuration."""

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging with a consistent, parseable format.

    Kept intentionally simple for the foundation slice; structured/JSON logging
    can be layered on when the platform ships to a real environment.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
