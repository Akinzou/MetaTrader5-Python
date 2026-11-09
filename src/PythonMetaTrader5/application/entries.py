"""Validated entry parameters shared by market and pending entries.

Split out of trader.py (300-line limit): this is the only place that turns raw
caller input into an entry request, so every check runs before any send.
"""

from __future__ import annotations

from dataclasses import dataclass

from PythonMetaTrader5.application.ports import Terminal
from PythonMetaTrader5.domain.errors import ErrorKind, TradeError
from PythonMetaTrader5.domain.inputs import positive_number, stop_input
from PythonMetaTrader5.domain.market import PendingKind
from PythonMetaTrader5.domain.orders import Side, validate_comment
from PythonMetaTrader5.domain.requests import CancelRequest, OrderRequest
from PythonMetaTrader5.domain.stops import Stop, StopKind
from PythonMetaTrader5.domain.symbol import SymbolSpec
from PythonMetaTrader5.result import Err, Ok, Result

StopInput = Stop | float | None


@dataclass(frozen=True, slots=True)
class Entry:
    spec: SymbolSpec
    side: Side
    volume: float
    comment: str
    stop_loss: Stop | None
    take_profit: Stop | None
    # The caller's price on the symbol's tick grid; None means "use the quote".
    price: float | None

    def request(
        self,
        quote: float | None = None,
        *,
        pending: PendingKind | None,
        deviation: int,
        magic: int,
    ) -> Result[OrderRequest | CancelRequest, TradeError]:
        reference = self.price if self.price is not None else quote
        if reference is None:
            return Err(TradeError(ErrorKind.NO_PRICE, f"no price for {self.spec.name}"))
        spec, side = self.spec, self.side
        sl = self.stop_loss.stop_loss(side, reference, spec) if self.stop_loss else Ok(None)
        if isinstance(sl, Err):
            return sl
        tp = self.take_profit.take_profit(side, reference, spec) if self.take_profit else Ok(None)
        if isinstance(tp, Err):
            return tp
        return Ok(
            OrderRequest(
                symbol=spec.name,
                side=side,
                volume=self.volume,
                price=reference,
                filling=spec.market_filling() if pending is None else spec.pending_filling(),
                deviation=deviation,
                magic=magic,
                comment=self.comment,
                sl=sl.value,
                tp=tp.value,
                pending=pending,
            )
        )


def validate_entry(
    terminal: Terminal,
    symbol: str,
    side: Side | str,
    volume: float,
    *,
    comment: str | None,
    sl: StopInput,
    tp: StopInput,
    price: object = None,
    price_required: bool = False,
) -> Result[Entry, TradeError]:
    # Every check that needs no terminal, the price included, runs before the
    # symbol lookup, which costs a round trip and may add the symbol to Market
    # Watch.
    values = _caller_values(side, comment, sl, tp, price, price_required=price_required)
    if isinstance(values, Err):
        return values
    amount = positive_number(volume, ErrorKind.INVALID_VOLUME, "volume")
    if isinstance(amount, Err):
        return amount
    spec = terminal.symbol(symbol)
    if isinstance(spec, Err):
        return spec
    lots = spec.value.validate_volume(amount.value)
    if isinstance(lots, Err):
        return lots
    parsed_side, text, stop_loss, take_profit, level = values.value
    on_grid = _quote_free_levels(spec.value, level, stop_loss, take_profit)
    if isinstance(on_grid, Err):
        return on_grid
    return Ok(
        Entry(spec.value, parsed_side, lots.value, text, stop_loss, take_profit, on_grid.value)
    )


def _quote_free_levels(
    spec: SymbolSpec, price: float | None, sl: Stop | None, tp: Stop | None
) -> Result[float | None, TradeError]:
    # Absolute stops do not depend on the quote, so they are checked here, before
    # the first tick request: otherwise a stop that can never be valid would sit
    # through the NO_PRICE retries of a symbol without quotes first.
    for name, stop in (("sl", sl), ("tp", tp)):
        if stop is not None and stop.kind is StopKind.PRICE:
            checked = spec.price_on_grid(stop.value, ErrorKind.INVALID_STOPS, name)
            if isinstance(checked, Err):
                return checked
    if price is None:
        return Ok(None)
    level = spec.price_on_grid(price, ErrorKind.INVALID_PRICE, "price")
    return level if isinstance(level, Err) else Ok(level.value)


def _caller_values(
    side: Side | str,
    comment: str | None,
    sl: StopInput,
    tp: StopInput,
    price: object,
    *,
    price_required: bool,
) -> Result[tuple[Side, str, Stop | None, Stop | None, float | None], TradeError]:
    parsed_side = Side.parse(side)
    if isinstance(parsed_side, Err):
        return parsed_side
    text = validate_comment(comment)
    if isinstance(text, Err):
        return text
    stop_loss, take_profit = stop_input(sl, "sl"), stop_input(tp, "tp")
    if isinstance(stop_loss, Err):
        return stop_loss
    if isinstance(take_profit, Err):
        return take_profit
    level = (
        positive_number(price, ErrorKind.INVALID_PRICE, "price")
        if price is not None or price_required
        else Ok(None)
    )
    if isinstance(level, Err):
        return level
    return Ok((parsed_side.value, text.value, stop_loss.value, take_profit.value, level.value))
