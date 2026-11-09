# ADR 0007: Filling mode from the symbol, prices on the tick grid

- Status: accepted (3.0.0); to be confirmed on more brokers with the demo tests

## Context

2.x sent FOK for entries and IOC for closes regardless of the symbol, and it
rounded prices to `digits`.

## Decision

Market orders use the first mode the symbol allows, in the order
FOK > IOC > RETURN. Pending orders follow the same rule, except on
exchange-execution symbols, where they use RETURN: there it is the only mode
that lets a limit order rest in the book. Prices snap to `trade_tick_size`
(falling back to `point`) and are then rounded to `digits`.

An earlier draft used a fixed RETURN for pending orders. We dropped it because
MQL5 documents RETURN as not allowed in Market execution mode, so on those
brokers every limit order would have been refused with 10030, while the IOC
that 2.x sent was accepted.

We prefer FOK over IOC because IOC can fill only part of the requested volume
and still report success, leaving a bot with a position size it never asked
for. Prices snap to the tick grid because rounding to `digits` produces prices
like 5780.13 on a 0.25-tick index, which the server rejects.

## Consequences

- Brokers that do not allow FOK no longer reject every order with 10030.
- A partial IOC fill is a `PARTIAL_FILL` error carrying the receipt (see ADR 0003).
