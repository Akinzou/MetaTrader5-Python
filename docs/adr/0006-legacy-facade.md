# ADR 0006: Keep a 2.x `Broker` facade; drop the star re-export

- Status: accepted (3.0.0)

## Context

The package has tens of thousands of downloads, and existing scripts call
`Broker(...)` and its CamelCase methods. 2.x also ran
`from MetaTrader5 import *` in its `__init__`, which re-exported the whole MT5
namespace.

## Decision

`PythonMetaTrader5.Broker` keeps the 2.x names, arguments and return shapes.
It delegates to `Trader` and emits a `DeprecationWarning`. The unsafe 2.x
behaviours are not reproduced (see MIGRATION.md). The star re-export is removed.

We chose a facade over keeping the 2.x code because the old code is exactly
the code that loops forever. We chose it over removing `Broker` because an
unattended bot upgraded by `pip install -U` would crash at import instead of
running safely. We dropped the re-export because shadowing MT5's namespace made
every new MT5 symbol part of our public API without any review.

## Consequences

- Old scripts keep running. Scripts that relied on re-exported MT5 names must
  import `MetaTrader5` directly.
