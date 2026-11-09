# ADR 0010: Keep re-exporting the MetaTrader5 namespace

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

`PythonMetaTrader5/__init__.py` re-exports every public name of the
installed `MetaTrader5` module, both as package attributes and in `__all__`,
so `from PythonMetaTrader5 import *` behaves as it did in 2.x.

- Our own names win a collision. Today the only one is `Tick`: ours is the
  quote model, while MT5's is its tick struct.
- Without the package (Linux, macOS, CI) nothing is re-exported, and the
  library still imports.
- `time`, loguru's `logger` and `pyautogui`, which 2.x also leaked, are not
  restored. The last two are no longer dependencies, and leaking a stdlib
  module is not an API.

## Consequences

- The ADR 0006 concern still holds: new MT5 releases add names to our
  namespace. The cost is bounded because our names win and nothing in the
  library uses the re-exported names.
- `import PythonMetaTrader5` now imports `MetaTrader5` eagerly. Importing it
  does not start or attach to a terminal; only `initialize()` does.
- `tests/contract` checks the star import against the real package.
