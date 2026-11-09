"""The one MetaTrader5 session of a process: how it is imported and locked.

Shared by the adapter and the 2.x namespace re-export, so both import the
package the same way and every call through either holds the same lock.
"""

from __future__ import annotations

import functools
import importlib
import threading
from collections.abc import Callable
from types import ModuleType
from typing import ParamSpec, TypeVar

# last_error() is process-global, so a call and the error read that explains it
# must not interleave with another thread's call. Module-level, not per adapter:
# connect() builds a new adapter each time, and every adapter and re-exported
# function in a process talks to the one MT5 session (ADR 0009).
SESSION = threading.RLock()
_P = ParamSpec("_P")
_R = TypeVar("_R")


def serialized(function: Callable[_P, _R]) -> Callable[_P, _R]:
    @functools.wraps(function)
    def locked(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with SESSION:
            return function(*args, **kwargs)

    return locked


def import_metatrader5() -> ModuleType | None:
    """The MetaTrader5 module, or None when it is not installed.

    Only "not installed" becomes None: it is the normal case outside Windows. A
    package that is installed but fails to import (a missing DLL, a numpy ABI
    mismatch) raises, so the real cause is reported where the names are used,
    instead of surfacing later as a NameError on symbol_info.
    """
    try:
        return importlib.import_module("MetaTrader5")
    except ModuleNotFoundError as error:
        if error.name == "MetaTrader5":
            return None
        raise
