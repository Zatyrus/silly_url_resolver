"""Independent mock server. Import DemoServer or run python -m url_caller_demo.

It uses only the standard library and never imports the caller or benchmark.
"""

from .server import DemoServer

__all__ = ["DemoServer"]
