"""The MetaTrader5 namespace, re-exported lazily for 2.x scripts (ADR 0010).

2.x ran ``from MetaTrader5 import *`` in its ``__init__``, and its own README
called ``symbol_info("EURUSD")`` after ``from PythonMetaTrader5 import *``.
The package ``__getattr__`` (PEP 562) delegates here, so MetaTrader5 is
imported only when one of its names is first used: importing the library, or
only its domain types, never depends on the MT5 wheel.
"""

from __future__ import annotations

import warnings
from types import ModuleType

from PythonMetaTrader5.adapters.mt5_session import import_metatrader5, serialized


def public_names() -> list[str]:
    module = _module_or_warn()
    if module is None:
        return []
    return sorted(n for n in dir(module) if not n.startswith("_"))


def resolve(name: str) -> object:
    """One MT5 name; functions are wrapped to hold the adapter's session lock.

    Without the lock a direct ``last_error()`` from a 2.x-style script could run
    between the adapter's ``order_send`` and its own ``last_error()`` read, and
    a lost order would be reported as "never sent" (ADR 0009). Only names not
    defined by the package reach this: a module __getattr__ runs on misses only.
    """
    try:
        module = None if name.startswith("_") else import_metatrader5()
    except ImportError as error:
        # AttributeError, not ImportError: hasattr(), getattr(.., default) and
        # IDE tooling must keep working on a broken install; the cause is kept.
        raise AttributeError(f"PythonMetaTrader5 has no attribute {name!r}: {error}") from error
    if module is None or not hasattr(module, name):
        raise AttributeError(f"module 'PythonMetaTrader5' has no attribute {name!r}")
    value = getattr(module, name)
    if callable(value) and not isinstance(value, type):
        return serialized(value)
    return value


def _module_or_warn() -> ModuleType | None:
    try:
        return import_metatrader5()
    except ImportError as error:
        # A star import of a broken install keeps our own names (connect() then
        # reports the failure as Err) and says loudly why the MT5 names are gone.
        warnings.warn(f"{error}; its names are not re-exported", RuntimeWarning, stacklevel=3)
        return None
