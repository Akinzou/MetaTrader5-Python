# ADR 0005: Standard logging, no NullHandler

- Status: accepted (3.0.0)

## Context

2.x logged with `loguru`, which writes to a global sink that the application
does not control. It also logged the full `account_info()`, including the
owner's name and balance.

## Decision

Use `logging.getLogger("PythonMetaTrader5")`, configure nothing, and log only
the login and server on connect.

We chose not to add the customary `NullHandler`. With it, an unconfigured
script swallows every ERROR record, so a failed order would leave no trace.
Without it, Python's last-resort handler still prints warnings and errors to
stderr.

## Consequences

- Applications control format and destination with standard tooling.
- 2.x users lose info-level console output unless they configure logging.
