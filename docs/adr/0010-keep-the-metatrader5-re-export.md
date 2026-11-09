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
  (a missing DLL or dependency, a numpy ABI mismatch raising ValueError or
  AttributeError) is turned into an `ImportError` with the cause. The star
  import then keeps our names and emits a `RuntimeWarning`, an MT5 name raises
  `AttributeError` carrying the cause (so `hasattr` and IDEs keep working),
  and `connect()` returns `Err(CONNECTION_FAILED)`. A raised `ImportError`
  would crash the star import even for scripts that only use `connect`.
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
- Re-exported functions are wrappers: `__wrapped__` is the MT5 original. They
  are resolved on every access (no cache), so `pkg.symbol_info is
  pkg.symbol_info` is False, and each access costs a few microseconds. The
  lock covers one call, not a sequence of a script's own calls.
- Known debt:
  - Neither resolved names nor the import outcome (missing or broken) are
    cached. Tools that probe many attributes repeat the import lookup, and on
    a broken install they re-run the failing import each time.
  - On a broken install, `hasattr` / `getattr(pkg, name, None)` give
    False / None without a warning; the cause is only in `__cause__` of the
    AttributeError. Star imports and `dir()` warn instead, and they raise
    under `-W error`. A 2.x script that uses an MT5 name after the star
    import still ends in a NameError; the RuntimeWarning beforehand names the
    cause.
- `tests/unit/test_mt5_namespace.py` covers the wiring with the fake module,
  and `tests/contract` covers the real one.
