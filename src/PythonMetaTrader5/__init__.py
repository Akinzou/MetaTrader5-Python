import time
from MetaTrader5 import *
from loguru import logger
import pyautogui


class Broker:
    RetCodes = {
        10027: "Enable Algo Trading in MetaTrader5 app",
        10018: "Market closed",
        10016: "Wrong SL",
    }

    log = None
    password = None
    server = None

    def __init__(self, log, password, server):
        self.log = log
        self.password = str(password)
        self.server = str(server)

        initialize()
        if login(self.log, self.password, server=self.server):
            logger.success("Login succes")
            acc_info = account_info()
            logger.info(str(acc_info))
        else:
            logger.error(f"Login failed: {self.log}")

    def login(self, ToEffect=False):
        while True:
            logger.info(f"Login on: {self.log}")
            if login(self.log, self.password, server=self.server):
                logger.success("OK")
                time.sleep(0.5)
                return True
            if ToEffect is False:
                logger.error("ERROR")
                return False

    # -------------------- Symbol meta & normalization --------------------

    def _symbol_meta(self, symbol):
        """
        Returns (point, digits).
        point  -> minimal price step (MT5)
        digits -> number of decimal places
        """
        info = symbol_info(symbol)
        if info is None:
            logger.error(f"{self.log}: symbol_info({symbol}) returned None")
            return None, None
        point = float(info.point)
        digits = int(info.digits)
        return point, digits

    def _normalize(self, price, digits):
        if price is None:
            return None
        step = 10 ** (-digits)
        return round(float(price) / step) * step

    # -------------------- Low-level senders --------------------

    def _RawOrderClose(self, order_type, symbol, volume, price, comment=None, ticket=None):
        order = {
            "action": TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(price),
            "deviation": 10,
            "type_filling": ORDER_FILLING_IOC,
        }
        if comment is not None:
            order["comment"] = comment
        if ticket is not None:
            order["position"] = ticket
        return order_send(order)

    def _RawOrder(self, order_type, symbol, volume, price, sl=None, tp=None, comment=None, ticket=None):
        volume = float(volume)

        # normalize prices to instrument digits before sending
        info = symbol_info(symbol)
        if info:
            digits = int(info.digits)
            price = self._normalize(price, digits)
            sl = self._normalize(sl, digits) if sl is not None else None
            tp = self._normalize(tp, digits) if tp is not None else None

        order = {
            "action": TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 10,
            "type_filling": ORDER_FILLING_FOK,
        }
        if comment is not None:
            order["comment"] = comment
        if ticket is not None:
            order["position"] = ticket
        if sl is not None:
            order["sl"] = float(sl)
        if tp is not None:
            order["tp"] = float(tp)
        return order_send(order)

    def _RawOrderLimit(self, order_type, symbol, volume, price, limit, comment=None, ticket=None):
        # MT5 uses 'price' for the pending level; keep signature consistent
        info = symbol_info(symbol)
        digits = int(info.digits) if info else 5
        limit = self._normalize(limit, digits)

        order = {
            "action": TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": float(limit),
            "deviation": 10,
            "type_filling": ORDER_FILLING_IOC,
        }
        if comment is not None:
            order["comment"] = comment
        if ticket is not None:
            order["position"] = ticket
        return order_send(order)

    # -------------------- Positions I/O --------------------

    def _pos_to_dict(self, p):
        """Serialize MT5 position to a dict (for as_dict=True)."""
        if p is None:
            return None
        return {
            "ticket": p.ticket,
            "symbol": p.symbol,
            "type": p.type,                 # ORDER_TYPE_BUY / ORDER_TYPE_SELL
            "volume": float(p.volume),
            "price_open": float(p.price_open),
            "sl": float(p.sl) if p.sl else None,
            "tp": float(p.tp) if p.tp else None,
            "price_current": float(p.price_current),
            "profit": float(p.profit),
            "time": int(p.time),            # epoch
            "magic": int(p.magic),
            "comment": p.comment,
        }

    # -------------------- Positions by symbol --------------------

    def GetPositionsBySymbol(self, symbol: str, as_dict: bool = False):
        """
        Return all open positions for the given symbol.
        If as_dict=True -> list of dictionaries.
        """
        try:
            positions = positions_get(symbol=symbol)
        except Exception as e:
            logger.error(f"{self.log}: GetPositionsBySymbol exception: {e}")
            return []

        positions = list(positions) if positions else []
        if as_dict:
            return [self._pos_to_dict(p) for p in positions]
        return positions

    def GetPositions(self, symbol=None, *, ticket=None, as_dict: bool = False):
        """
        Return positions with the same filtering semantics as Close():
        - if ticket is provided -> only that position
        - elif symbol is provided -> all positions for that symbol
        - else -> all open positions
        """
        try:
            if ticket is not None:
                pos = positions_get(ticket=ticket)
            elif symbol is not None:
                pos = positions_get(symbol=symbol)
            else:
                pos = positions_get()
        except Exception as e:
            logger.error(f"{self.log}: GetPositions exception: {e}")
            return []

        pos = list(pos) if pos else []
        if as_dict:
            return [self._pos_to_dict(p) for p in pos]
        return pos

    def GetPosition(self, symbol=None, *, ticket=None, as_dict: bool = False):
        """
        Return the first matching position or None.
        Convenient when you expect at most one.
        """
        pos_list = self.GetPositions(symbol=symbol, ticket=ticket, as_dict=False)
        if not pos_list:
            return None if not as_dict else None
        return self._pos_to_dict(pos_list[0]) if as_dict else pos_list[0]

    # -------------------- SL/TP computation: absolute or offset IN POINTS --------------------

    def _compute_sl_tp(self, order_type, symbol, sl, tp, sl_type: str, tp_type: str):
        """
        Return (sl_val, tp_val) as absolute prices.
        - 'absolute' -> values are prices (e.g., 1.12345), only normalized
        - 'offset'   -> values are POINTS away from the current price:
                        BUY : SL = ask - |sl|*point,  TP = ask + |tp|*point
                        SELL: SL = bid + |sl|*point,  TP = bid - |tp|*point
        """
        sl_val = float(sl) if sl is not None else None
        tp_val = float(tp) if tp is not None else None
        sl_type = (sl_type or "absolute").lower()
        tp_type = (tp_type or "absolute").lower()

        info_tick = symbol_info_tick(symbol)
        if info_tick is None:
            logger.error(f"{self.log}: symbol_info_tick({symbol}) returned None (SL/TP compute)")
            return None, None

        point, digits = self._symbol_meta(symbol)
        if point is None:
            return None, None

        is_buy = (order_type == ORDER_TYPE_BUY)
        ref_price = info_tick.ask if is_buy else info_tick.bid

        if sl_val is not None:
            if sl_type == "absolute":
                pass
            elif sl_type == "offset":
                sl_val = ref_price - abs(sl_val) * point if is_buy else ref_price + abs(sl_val) * point
            else:
                logger.error(f"{self.log}: invalid sl_type '{sl_type}' (use 'absolute'|'offset')")
                return None, None

        if tp_val is not None:
            if tp_type == "absolute":
                pass
            elif tp_type == "offset":
                tp_val = ref_price + abs(tp_val) * point if is_buy else ref_price - abs(tp_val) * point
            else:
                logger.error(f"{self.log}: invalid tp_type '{tp_type}' (use 'absolute'|'offset')")
                return None, None

        sl_val = self._normalize(sl_val, digits) if sl_val is not None else None
        tp_val = self._normalize(tp_val, digits) if tp_val is not None else None
        return sl_val, tp_val

    # -------------------- Single market-entry function --------------------

    def OpenPosition(
        self,
        symbol,
        side,
        volume,
        *,
        sl=None,
        tp=None,
        price=None,
        comment=None,
        ticket=None,
        sl_type: str = "absolute",  # 'absolute' (price) or 'offset' (POINTS)
        tp_type: str = "absolute",  # 'absolute' (price) or 'offset' (POINTS)
    ):
        """
        Open a market position.
        side: "buy"/"sell" (also accepts "long"/"short")
        SL/TP:
          - sl_type/tp_type == 'absolute': pass absolute prices
          - sl_type/tp_type == 'offset'  : pass POINTS from current price
        price: if None -> use current ask/bid and retry on known transient errors
        """
        side = str(side).lower()
        if side not in ("buy", "sell", "long", "short"):
            logger.error(f"{self.log}: invalid side '{side}' (use 'buy'/'sell')")
            return None

        order_type = ORDER_TYPE_BUY if side in ("buy", "long") else ORDER_TYPE_SELL

        sl_val, tp_val = self._compute_sl_tp(order_type, symbol, sl, tp, sl_type, tp_type)

        # direct-price mode
        if price is not None:
            return self._RawOrder(order_type, symbol, volume, price, sl_val, tp_val, comment, ticket)

        # current-tick mode with retries
        while True:
            info = symbol_info_tick(symbol)
            if info is None:
                logger.error(f"{self.log}: symbol_info_tick({symbol}) returned None")
                return None

            curr_price = info.ask if order_type == ORDER_TYPE_BUY else info.bid
            r = self._RawOrder(order_type, symbol, volume, curr_price, sl_val, tp_val, comment, ticket)

            if r is None:
                logger.error(f"{self.log}: order_send returned None")
                return None

            if r.retcode == TRADE_RETCODE_DONE or r.retcode == 10009:
                action = "long" if order_type == ORDER_TYPE_BUY else "short"
                details = []
                if sl_val is not None:
                    details.append(f"SL {sl_val}")
                if tp_val is not None:
                    details.append(f"TP {tp_val}")
                suffix = f" ({', '.join(details)})" if details else ""
                logger.success(f"{self.log}: {action} {symbol}{suffix}")
                return r

            if r.retcode in self.RetCodes:
                action = "long" if order_type == ORDER_TYPE_BUY else "short"
                logger.error(f"ERROR CAN NOT OPEN {self.log}: {action} {symbol}")
                logger.error(self.RetCodes[r.retcode])
                if r.retcode == 10027:
                    logger.info(f"Enabling algotrading {self.log} {symbol}")
                    time.sleep(1)
                    pyautogui.hotkey("ctrl", "e")
                if r.retcode == 10016:
                    return r
                time.sleep(0.5)
            else:
                action = "long" if order_type == ORDER_TYPE_BUY else "short"
                logger.error(f"ERROR CAN NOT OPEN TRYING AGAIN {self.log}: {action} {symbol}")
                logger.info(f"RetCode: {r.retcode}")
                logger.info(f"Comment: {r.comment}")
                time.sleep(0.5)

    # -------------------- Backward-compat wrappers --------------------

    def Buy(self, symbol, volume, price=None, *, comment=None, ticket=None):
        return self.OpenPosition(symbol, "buy", volume, price=price, comment=comment, ticket=ticket)

    def BuySL(self, symbol, volume, sl, price=None, *, comment=None, ticket=None, sl_type: str = "absolute"):
        return self.OpenPosition(
            symbol, "buy", volume, sl=sl, price=price, comment=comment, ticket=ticket, sl_type=sl_type
        )

    def Sell(self, symbol, volume, price=None, *, comment=None, ticket=None):
        return self.OpenPosition(symbol, "sell", volume, price=price, comment=comment, ticket=ticket)

    def SellSL(self, symbol, volume, sl, price=None, *, comment=None, ticket=None, sl_type: str = "absolute"):
        return self.OpenPosition(
            symbol, "sell", volume, sl=sl, price=price, comment=comment, ticket=ticket, sl_type=sl_type
        )

    # -------------------- Closing logic --------------------

    def Close(self, symbol, *, comment=None, ticket=None):
        close = False
        if ticket is not None:
            positions = positions_get(ticket=ticket)
        else:
            positions = positions_get(symbol=symbol)

        lenpositions = len(positions)
        if positions:
            while True:
                for pos in positions:
                    if pos.type == ORDER_TYPE_BUY or pos.type == ORDER_TYPE_SELL:
                        for _ in range(10):
                            info = symbol_info_tick(symbol)
                            if info is None:
                                return None
                            if pos.type == ORDER_TYPE_BUY:
                                r = self._RawOrderClose(
                                    ORDER_TYPE_SELL, symbol, pos.volume, info.bid, comment, pos.ticket
                                )
                                close = True
                            else:
                                r = self._RawOrderClose(
                                    ORDER_TYPE_BUY, symbol, pos.volume, info.ask, comment, pos.ticket
                                )
                                close = True
                            if r is None:
                                return None
                            if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
                                if r.retcode == TRADE_RETCODE_DONE:
                                    logger.info(f"{self.log}: closing all {symbol}")
                                    lenpositions -= 1
                                    break
                        if r.retcode in self.RetCodes:
                            logger.error(f"ERROR CAN NOT CLOSE {self.log} {symbol}")
                            logger.error(self.RetCodes[r.retcode])
                            time.sleep(0.5)
                if not lenpositions:
                    break
                if r.retcode == 10027:
                    logger.info(f"Enabling algotrading {self.log} {symbol}")
                    time.sleep(1)
                    pyautogui.hotkey("ctrl", "e")

        if not close:
            logger.info(f"{self.log}: there is no orders to close")
        return False

    # -------------------- Pending orders --------------------

    def SellLimit(self, symbol, volume, stoplimit, price=None, comment=None, ticket=None):
        OpenedInstantly = False
        if price is not None:
            logger.error("Price have to be none")
            return

        while True:
            info = symbol_info_tick(symbol)
            if float(info.bid) >= float(stoplimit):
                r = self._RawOrder(ORDER_TYPE_SELL, symbol, float(volume), info.bid, comment=comment, ticket=ticket)
                OpenedInstantly = True
            else:
                r = self._RawOrderLimit(
                    ORDER_TYPE_SELL_LIMIT, symbol, float(volume), info.bid, float(stoplimit), comment, ticket
                )
                OpenedInstantly = False

            if r.retcode == 10009:
                if OpenedInstantly:
                    logger.success(f"{self.log}: opened short on: {symbol} beacues of ask is > or = limit price")
                else:
                    logger.success(f"{self.log}: opened short limit on: {symbol}  price: {stoplimit}")
                break
            else:
                if r.retcode in self.RetCodes:
                    logger.error(f"ERROR CAN NOT OPEN {self.log}  sell limit on: {symbol}  price: {stoplimit}")
                    logger.error(self.RetCodes[r.retcode])
                    if r.retcode == 10027:
                        logger.info(f"Enabling algotrading {self.log} {symbol}")
                        time.sleep(1)
                        pyautogui.hotkey("ctrl", "e")
                    time.sleep(0.5)
                else:
                    logger.error(
                        f"ERROR CAN NOT OPEN TRYING AGAIN {self.log}  sell limit on: {symbol}  price: {stoplimit}"
                    )
                    logger.info(f"RetCode: {r.retcode}")
                    logger.info(f"Comment: {r.comment}")
                    time.sleep(0.5)
        return r

    def BuyLimit(self, symbol, volume, stoplimit, price=None, comment=None, ticket=None):
        OpenedInstantly = False
        if price is not None:
            logger.error("Price have to be none")
            return

        while True:
            info = symbol_info_tick(symbol)
            if float(info.ask) <= float(stoplimit):
                r = self._RawOrder(ORDER_TYPE_BUY, symbol, float(volume), info.ask, comment=comment, ticket=ticket)
                OpenedInstantly = True
            else:
                r = self._RawOrderLimit(
                    ORDER_TYPE_BUY_LIMIT, symbol, float(volume), info.ask, float(stoplimit), comment, ticket
                )
                OpenedInstantly = False

            if r.retcode == 10009:
                if OpenedInstantly:
                    logger.success(f"{self.log}: opened long on: {symbol} beacues of ask is < or = limit price")
                else:
                    logger.success(f"{self.log}: opened long limit on: {symbol}  price: {stoplimit}")
                break
            else:
                if r.retcode in self.RetCodes:
                    logger.error(f"ERROR CAN NOT OPEN {self.log}  long limit on: {symbol}  price: {stoplimit}")
                    logger.error(self.RetCodes[r.retcode])
                    if r.retcode == 10027:
                        logger.info(f"Enabling algotrading {self.log} {symbol}")
                        time.sleep(1)
                        pyautogui.hotkey("ctrl", "e")
                    time.sleep(0.5)
                else:
                    logger.error(
                        f"ERROR CAN NOT OPEN TRYING AGAIN {self.log}  long limit on: {symbol}  price: {stoplimit}"
                    )
                    logger.info(f"RetCode: {r.retcode}")
                    logger.info(f"Comment: {r.comment}")
                    time.sleep(0.5)
        return r

    # -------------------- Cancel pending orders --------------------

    def _RawCancelOrder(self, order_number):
        request = {
            "action": TRADE_ACTION_REMOVE,
            "order": order_number,
            "comment": "Order Removed",
        }
        return order_send(request)

    def CancelOrders(self, symbol):
        orders = orders_get()
        limit_orders = [
            order
            for order in orders
            if order.type == ORDER_TYPE_BUY_LIMIT or order.type == ORDER_TYPE_SELL_LIMIT
        ]
        lenpositions = len(limit_orders)

        while True:
            r = None
            for order in limit_orders:
                if order.symbol == symbol:
                    r = self._RawCancelOrder(order.ticket)

                    if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
                        if r.retcode == TRADE_RETCODE_DONE:
                            logger.info(f"{self.log}: order have been just cancelled on: {symbol}")
                            lenpositions -= 1
                            break
                    if r.retcode in self.RetCodes:
                        logger.error(f"ERROR CAN NOT CLOSE {self.log} {symbol}")
                        logger.error(self.RetCodes[r.retcode])
                        time.sleep(0.5)

            if not lenpositions:
                break
            if r is not None and r.retcode == 10027:
                logger.info(f"Enabling algotrading {self.log} {symbol}")
                time.sleep(1)
                pyautogui.hotkey("ctrl", "e")

        if not len(limit_orders):
            logger.info(f"{self.log}: there is no orders to cancel")

    # -------------------- Disconnect --------------------

    def Disconnect(self):
        shutdown()
        logger.info("Disconnected from MT5")
