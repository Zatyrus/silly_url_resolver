"""Public API: Schedule, TimedBrowserCaller and CallResult.

Importing this package opens no browser and starts no server or process.
"""

from .caller import TimedBrowserCaller
from .result import CallResult
from .schedule import Schedule

__version__ = "0.5.0"
__all__ = ["Schedule", "TimedBrowserCaller", "CallResult"]
