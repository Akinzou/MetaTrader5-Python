# ADR 0001: Ports only at process boundaries

- Status: accepted (3.0.0)

## Context

2.x called `MetaTrader5` functions from one 535-line class, so every rule
(price rounding, stop maths, retry decisions) needed a live terminal to test.

## Decision

Two ports, `Terminal` and `Clock`, one per process boundary. Everything that
does no I/O is a plain function or a method on a domain object.

We chose one port per boundary over one port per concern (e.g. separate
`PriceFeed` and `OrderGateway`). Both concerns go over the same IPC channel to
one terminal process. Splitting them would let tests fake an impossible state
(quotes from one terminal, orders sent to another) and would hide that a single
`shutdown()` ends both.

## Consequences

- Unit tests run on any OS against `FakeTerminal`.
- The MT5 adapter is the only module that knows MT5 request dictionaries.
