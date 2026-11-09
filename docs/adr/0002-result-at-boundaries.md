# ADR 0002: Result values at boundaries, exceptions for programming errors

- Status: accepted (3.0.0)

## Context

Most trading failures are expected (market closed, no money, requote). 2.x
mixed `None`, `False`, raw MT5 results and endless loops.

## Decision

Use cases and ports return `Ok(value)` or `Err(error)`. `TradeError` carries an
`ErrorKind`, the retcode and the broker's receipt. Batch operations return a
`BatchFailure` with the outcome of each ticket. Exceptions are raised only for
programming errors, such as an invalid `RetryPolicy`.

We chose a small in-house `Result` over the `returns` library because that
library would add a runtime dependency and a mypy plugin to every user's
project for the sake of two dataclasses. We chose it over exceptions because
an unhandled `MarketClosedError` in a webhook handler silently drops the signal.

## Consequences

- Callers have to look at the outcome; `match` statements read naturally.
- A batch close never reports "done" while some positions are still open.
