"""The MetaTrader5 namespace, re-exported lazily for 2.x scripts (ADR 0010).

2.x ran ``from MetaTrader5 import *`` in its ``__init__``, and its own README
called ``symbol_info("EURUSD")`` after ``from PythonMetaTrader5 import *``.
The package ``__getattr__`` (PEP 562) delegates here, so MetaTrader5 is
imported only when one of its names is first used: importing the library, or
only its domain types, never depends on the MT5 wheel.
"""

from __future__ import annotations

from collections.abc import Collection

from PythonMetaTrader5.adapters.mt5_session import import_metatrader5, serialized


def public_names(*, taken: Collection[str]) -> list[str]:
    module = import_metatrader5()
    if module is None:
        return []
    return sorted(n for n in dir(module) if not n.startswith("_") and n not in taken)


def resolve(name: str, *, taken: Collection[str]) -> object:
    """One MT5 name; functions are wrapped to hold the adapter's session lock.

    Without the lock a direct ``last_error()`` from a 2.x-style script could run
    between the adapter's ``order_send`` and its own ``last_error()`` read, and
    a lost order would be reported as "never sent" (ADR 0009).
    """
    module = None if name.startswith("_") or name in taken else import_metatrader5()
    if module is None or not hasattr(module, name):
        raise AttributeError(f"module 'PythonMetaTrader5' has no attribute {name!r}")
    value = getattr(module, name)
    if callable(value) and not isinstance(value, type):
        return serialized(value)
    return value
