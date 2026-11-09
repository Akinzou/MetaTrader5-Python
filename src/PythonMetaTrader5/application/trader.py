"""Trading use cases: open, close, place and cancel orders, query state."""

from __future__ import annotations

from dataclasses import replace
from types import TracebackType

from PythonMetaTrader5.application.batch import BatchFailure, run_batch, with_magic
from PythonMetaTrader5.application.entries import StopInput, validate_entry
from PythonMetaTrader5.application.execution import RetryPolicy, execute
from PythonMetaTrader5.application.ports import Clock, Terminal
from PythonMetaTrader5.domain.errors import TradeError
from PythonMetaTrader5.domain.inputs import symbol_filter, ticket_filter
from PythonMetaTrader5.domain.market import PendingKind, PendingOrder, Position, TradeReceipt
from PythonMetaTrader5.domain.orders import Side, validate_comment
from PythonMetaTrader5.domain.requests import CancelRequest, OrderRequest
from PythonMetaTrader5.domain.symbol import SymbolSpec
from PythonMetaTrader5.result import Err, Ok, Result


class Trader:
    def __init__(
        self,
        terminal: Terminal,
        clock: Clock,
        *,
        magic: int = 0,
        deviation: int = 10,
        retry: RetryPolicy | None = None,
    ) -> None:
        self._terminal = terminal
        self._clock = clock
        self._magic = magic
        self._deviation = deviation
        self._retry = retry or RetryPolicy()

    # ------------------------------------------------------------------ entries

    def open_position(
        self,
        symbol: str,
        side: Side | str,
        volume: float,
        *,
        sl: StopInput = None,
        tp: StopInput = None,
        price: float | None = None,
        comment: str | None = None,
    ) -> Result[TradeReceipt, TradeError]:
        """Open a market position; ``sl``/``tp`` floats are prices, ``Stop.points`` distances.

        Without ``price`` the current quote is used and requotes are retried with a
        fresh quote. An explicit ``price`` is sent once: re-sending the same price
        after a requote cannot succeed.
        """
        entry = validate_entry(
            self._terminal, symbol, side, volume, comment=comment, sl=sl, tp=tp, price=price
        )
        if isinstance(entry, Err):
            return entry
        e = entry.value

        def build() -> Result[OrderRequest | CancelRequest, TradeError]:
            quote = None
            if e.price is None:
                tick = self._terminal.tick(symbol)
                if isinstance(tick, Err):
                    return tick
                quote = tick.value.entry_price(e.side)
            return e.request(quote, pending=None, deviation=self._deviation, magic=self._magic)

        policy = self._retry if e.price is None else replace(self._retry, attempts=1)
        return execute(self._terminal, self._clock, build, policy)

    def place_limit_order(
        self,
        symbol: str,
        side: Side | str,
        volume: float,
        price: float,
        *,
        sl: StopInput = None,
        tp: StopInput = None,
        comment: str | None = None,
    ) -> Result[TradeReceipt, TradeError]:
        """Place a BUY/SELL LIMIT at ``price``; point stops are measured from that level.

        A limit on the wrong side of the market is refused by the server
        (INVALID_PRICE) rather than converted into a market order.
        """
        entry = validate_entry(
            self._terminal,
            symbol,
            side,
            volume,
            comment=comment,
            sl=sl,
            tp=tp,
            price=price,
            price_required=True,
        )
        if isinstance(entry, Err):
            return entry
        request = entry.value.request(
            pending=PendingKind.LIMIT, deviation=self._deviation, magic=self._magic
        )
        if isinstance(request, Err):
            return request
        return execute(self._terminal, self._clock, lambda: request, self._retry)

    # ------------------------------------------------------------------- exits

    def close_positions(
        self,
        symbol: str | None = None,
        *,
        ticket: int | None = None,
        magic: int | None = None,
        comment: str | None = None,
    ) -> Result[list[TradeReceipt], BatchFailure]:
        """Close matching positions; ``ticket`` takes precedence over ``symbol``.

        With neither ``symbol``, ``ticket`` nor ``magic`` this closes EVERY position
        on the account, manual ones included. Pass ``magic`` to touch only your own.
        """
        text = validate_comment(comment)
        if isinstance(text, Err):
            return Err(BatchFailure((), (text.error,)))
        listed = self.positions(None if ticket is not None else symbol, ticket=ticket, magic=magic)
        if isinstance(listed, Err):
            return Err(BatchFailure((), (listed.error,)))
        # One spec lookup per symbol, not per position: close-all is time-critical.
        specs: dict[str, Result[SymbolSpec, TradeError]] = {}

        def close(position: Position) -> Result[TradeReceipt, TradeError]:
            if position.symbol not in specs:
                specs[position.symbol] = self._terminal.symbol(position.symbol)
            return self._close_one(position, specs[position.symbol], text.value)

        return run_batch(listed.value, close)

    def cancel_pending_orders(
        self,
        symbol: str | None = None,
        *,
        magic: int | None = None,
        kind: PendingKind | None = None,
    ) -> Result[list[TradeReceipt], BatchFailure]:
        listed = self.pending_orders(symbol, magic=magic, kind=kind)
        if isinstance(listed, Err):
            return Err(BatchFailure((), (listed.error,)))
        return run_batch(listed.value, self._cancel_one)

    # ----------------------------------------------------------------- queries

    def positions(
        self, symbol: str | None = None, *, ticket: int | None = None, magic: int | None = None
    ) -> Result[list[Position], TradeError]:
        for check in (symbol_filter(symbol), ticket_filter(ticket)):
            if isinstance(check, Err):
                return check
        listed = self._terminal.positions(symbol=symbol, ticket=ticket)
        return listed if isinstance(listed, Err) else Ok(with_magic(listed.value, magic))

    def pending_orders(
        self,
        symbol: str | None = None,
        *,
        magic: int | None = None,
        kind: PendingKind | None = None,
    ) -> Result[list[PendingOrder], TradeError]:
        checked = symbol_filter(symbol)
        if isinstance(checked, Err):
            return checked
        listed = self._terminal.pending_orders(symbol=symbol)
        if isinstance(listed, Err):
            return listed
        orders = with_magic(listed.value, magic)
        return Ok(orders if kind is None else [o for o in orders if o.kind is kind])

    def shutdown(self) -> None:
        self._terminal.shutdown()

    def __enter__(self) -> Trader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.shutdown()

    # ----------------------------------------------------------------- helpers

    def _close_one(
        self, position: Position, spec: Result[SymbolSpec, TradeError], comment: str
    ) -> Result[TradeReceipt, TradeError]:
        if isinstance(spec, Err):
            return spec
        filling = spec.value.market_filling()

        def build() -> Result[OrderRequest | CancelRequest, TradeError]:
            tick = self._terminal.tick(position.symbol)
            if isinstance(tick, Err):
                return tick
            return Ok(
                OrderRequest(
                    symbol=position.symbol,
                    side=position.side.opposite,
                    volume=position.volume,
                    price=tick.value.exit_price(position.side),
                    filling=filling,
                    deviation=self._deviation,
                    magic=self._magic,
                    comment=comment,
                    position=position.ticket,
                )
            )

        return execute(self._terminal, self._clock, build, self._retry)

    def _cancel_one(self, order: PendingOrder) -> Result[TradeReceipt, TradeError]:
        request = CancelRequest(order=order.ticket)
        return execute(self._terminal, self._clock, lambda: Ok(request), self._retry)
