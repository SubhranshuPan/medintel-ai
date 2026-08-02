"""Test package.

Settings default to ``production`` (``app.core.config``), which refuses the
placeholder JWT secret. This package is imported before ``conftest.py`` and any
``app`` module, so it is the earliest point at which the suite can declare its
own environment.
"""

import os

os.environ.setdefault("MEDINTEL_ENVIRONMENT", "test")
