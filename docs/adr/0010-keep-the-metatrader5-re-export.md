# ADR 0010: Keep re-exporting the MetaTrader5 namespace, lazily

- Status: accepted (3.0.0). Supersedes the "drop the star re-export" part
  of [ADR 0006](0006-legacy-facade.md).

## Context

ADR 0006 removed the `from MetaTrader5 import *` that 2.x ran in its
`__init__`. Its reason was that every new MT5 name became part of our public
API without review. But 2.x's own README called `symbol_info("EURUSD")` after
`from PythonMetaTrader5 import *`, so scripts written from that README would
fail with `NameError` after a plain `pip install -U`. The package owner
asked to keep the names.

## Decision

The package defines a module `__getattr__` (PEP 562). Our own names are
regular module attributes and always win, e.g. `Tick` (ours is the quote
model, MT5's is its tick struct). Any other public name is looked up in
`MetaTrader5` on first use. A star import asks for `__all__` through the same
hook and gets our names plus MT5's.

- **Lazy.** We rejected the first draft, which ran `from MetaTrader5 import *`
  eagerly in `__init__`. It made every `import PythonMetaTrader5` (even of
  the pure domain types) pay for MT5 and numpy, and fail with them: a numpy
  ABI mismatch would have broken the import itself.
- **Missing vs broken.** "Not installed" (the normal case outside Windows)
  means MT5 contributes no names. An installed package that fails to import
  (a missing DLL or dependency) raises where an MT5 name is used, with the
  real cause, instead of turning into a `NameError` later.
  `adapters/mt5_session.import_metatrader5` is the one import site, shared
  with the adapter.
- **Locked.** Re-exported functions run under the adapter's process-wide
  session lock (ADR 0009). Otherwise a direct `last_error()` could run
  between the adapter's `order_send` and its own `last_error()` read, and a
  lost order would be reported as "never sent".
- `time`, loguru's `logger` and `pyautogui`, which 2.x also leaked, are not
  restored. The last two are no longer dependencies, and leaking a stdlib
  module is not an API.

## Consequences

- New MT5 releases add names to our namespace, as ADR 0006 warned. The cost is
  bounded: our names win, and nothing in the library uses the re-exports.
- An MT5 name that equals one of our submodules (`result`, `connection`, ...)
  resolves to the submodule. None does today.
- For type checkers, the module `__getattr__` returns `Any`, so
  `from PythonMetaTrader5 import symbol_info` type-checks, but so does a typo
  like `PythonMetaTrader5.Trder`. Our own names keep their real types.
- Re-exported functions are wrappers: `__wrapped__` is the MT5 original.
- `tests/unit/test_mt5_namespace.py` covers the wiring with the fake module,
  and `tests/contract` covers the real one.
