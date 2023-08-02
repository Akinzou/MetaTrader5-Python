# internal order send
from MetaTrader5 import *
import colorama

def SpacerStart():
    print(colorama.Style.RESET_ALL + "//////////////////////////////")

def SpacerEnd():
    print(colorama.Style.RESET_ALL + "//////////////////////////////")
    print()

class Broker:
    log = None
    password = None
    server = None
    def __init__(self, log, password, server):
        initialize()
        if login(log, str(password), server=str(server)):
            print(colorama.Fore.GREEN + "Login succes")
            acc_info = account_info()
            print(colorama.Style.RESET_ALL + str(acc_info))
            self.log = log
            self.password = str(password)
            self.server = str(server)

        else:
            print("Login failed")

    def login(self):
        print(colorama.Fore.YELLOW + "Login on: ", str(self.log))
        if login(self.log, self.password, server=self.server):
            print(colorama.Fore.GREEN + "OK")
        else:
            print(colorama.Fore.RED + "ERROR")

    def _RawOrderClose(self, order_type, symbol, volume, price, comment=None, ticket=None):
        order = {
            "action": TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 10,
        }
        if comment is not None:
            order["comment"] = comment
        if ticket is not None:
            order["position"] = ticket
        return order_send(order)


    def _RawOrder(self, order_type, symbol, volume, price, sl=None, comment=None, ticket=None):
        volume = float(volume)
        order = {
            "action": TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 10
            # "type_filling": ORDER_FILLING_IOC
        }
        if comment is not None:
            order["comment"] = comment
        if ticket is not None:
            order["position"] = ticket

        if sl is not None:
            sl = float(sl)
            order["sl"] = sl

        return order_send(order)


    def _RawOrderLimit(self, order_type, symbol, volume, price, limit, comment=None, ticket=None):
        limit = float(limit)
        volume = float(volume)
        order = {
            "action": TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": limit,
            "deviation": 10
            # "type_filling": ORDER_FILLING_IOC
        }
        if comment is not None:
            order["comment"] = comment
        if ticket is not None:
            order["position"] = ticket

        return order_send(order)

    # Close all specific orders
    def Close(self, symbol, *, comment=None, ticket=None):
        SpacerStart()
        close = False
        if ticket is not None:
            positions = positions_get(ticket=ticket)
        else:
            positions = positions_get(symbol=symbol)

        tried = 0
        done = 0

        for pos in positions:
            # process only simple buy, sell
            if pos.type == ORDER_TYPE_BUY or pos.type == ORDER_TYPE_SELL:
                tried += 1
                for tries in range(10):
                    info = symbol_info_tick(symbol)
                    if info is None:
                        return None
                    if pos.type == ORDER_TYPE_BUY:
                        r = self._RawOrderClose(ORDER_TYPE_SELL, symbol, pos.volume, info.bid, comment, pos.ticket)
                        print(colorama.Fore.BLUE + str(self.log), ": closing all ", symbol)
                        close = True
                    else:
                        r = self._RawOrderClose(ORDER_TYPE_BUY, symbol, pos.volume, info.ask, comment, pos.ticket)
                        print(colorama.Fore.BLUE + str(self.log), ": closing all ", symbol)
                        close = True
                    # check results
                    if r is None:
                        return None
                    if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
                        if r.retcode == TRADE_RETCODE_DONE:
                            done += 1
                        break
        if not close:
            print(str(self.log), ": there is no orders to close")
        SpacerEnd()

        if done > 0:
            if done == tried:
                return True
            else:
                return "Partially"
        return False


    # Buy order
    def Buy(self, symbol, volume, price=None, *, comment=None, ticket=None):
        SpacerStart()
        print(colorama.Fore.GREEN + str(self.log), ": long ", symbol)
        SpacerEnd()
        # with direct call
        if price is not None:
            return self._RawOrder(ORDER_TYPE_BUY, symbol, volume, price, comment, ticket)
        # no price, we try several times with current price
        for tries in range(10):
            info = symbol_info_tick(symbol)
            r = self._RawOrder(ORDER_TYPE_BUY, symbol, volume, info.ask, comment, ticket)
            if r is None:
                return None
            if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
                break
        return r


    def BuySL(self, symbol, volume, sl, price=None, *, comment=None, ticket=None):
        SpacerStart()
        print(colorama.Fore.GREEN + str(self.log), ": long ", symbol, " sl ", sl)
        SpacerEnd()
        # with direct call
        if price is not None:
            return self._RawOrder(ORDER_TYPE_BUY, symbol, volume, price, sl, comment, ticket)
        # no price, we try several times with current price
        for tries in range(10):
            info = symbol_info_tick(symbol)
            r = self._RawOrder(ORDER_TYPE_BUY, symbol, volume, info.ask, sl, comment, ticket)
            if r is None:
                return None
            if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
                break
        return r


    # Sell order
    def Sell(self, symbol, volume, price=None, *, comment=None, ticket=None):
        SpacerStart()
        print(colorama.Fore.RED + str(self.log), ": short ", symbol)
        SpacerEnd()
        # with direct call
        if price is not None:
            return self._RawOrder(ORDER_TYPE_SELL, symbol, volume, price, comment, ticket)
        # no price, we try several times with current price
        for tries in range(10):
            info = symbol_info_tick(symbol)
            r = self._RawOrder(ORDER_TYPE_SELL, symbol, volume, info.bid, comment, ticket)
            if r is None:
                return None
            if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
                break
        return r


    def SellSL(self, symbol, volume, sl, price=None, *, comment=None, ticket=None):
        SpacerStart()
        print(colorama.Fore.RED + str(self.log), ": short ", symbol, " sl ", sl)
        SpacerEnd()
        # with direct call
        if price is not None:
            return self._RawOrder(ORDER_TYPE_SELL, symbol, volume, price, float(sl), comment, ticket)
        # no price, we try several times with current price
        for tries in range(10):
            info = symbol_info_tick(symbol)
            r = self._RawOrder(ORDER_TYPE_SELL, symbol, volume, info.bid, float(sl), comment, ticket)
            if r is None:
                return None
            if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
                break
        return r


    def SellLimit(self, symbol, volume, stoplimit, price=None, comment=None, ticket=None):
        # with direct call
        SpacerStart()
        if price is not None:
            return print("Price have to be none")
        # no price, we try several times with current price
        for tries in range(10):
            info = symbol_info_tick(symbol)
            if (float(info.bid) >= float(stoplimit)):
                r = self._RawOrder(ORDER_TYPE_SELL, symbol, float(volume), info.bid, comment, ticket)
                print(colorama.Fore.RED + str(self.log), ": opened short on: ", symbol, "beacues of ask is > or = limit price")
            else:
                r = self._RawOrderLimit(ORDER_TYPE_SELL_LIMIT, symbol, float(volume), info.bid, float(stoplimit), comment,
                                   ticket)
                print(colorama.Fore.RED + str(self.log), ": opened short limit on: ", symbol, " price: ", stoplimit)
            SpacerEnd()
            if r is None:
                return None
            if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
                break
        return r


    def BuyLimit(self, symbol, volume, stoplimit, price=None, comment=None, ticket=None):
        SpacerStart()
        if price is not None:
            return self._RawOrderLimit(ORDER_TYPE_BUY_LIMIT, symbol, float(volume), price, float(stoplimit), comment, ticket)
        # no price, we try several times with current price
        for tries in range(10):
            info = symbol_info_tick(symbol)
            if (float(info.ask) <= float(stoplimit)):
                r = self._RawOrder(ORDER_TYPE_BUY, symbol, float(volume), info.ask, comment, ticket)
                print(colorama.Fore.GREEN + str(self.log), ": opened long on: ", symbol, "beacues of ask is < or = limit price")
            else:
                r = self._RawOrderLimit(ORDER_TYPE_BUY_LIMIT, symbol, float(volume), info.ask, float(stoplimit), comment, ticket)
                print(colorama.Fore.GREEN + str(self.log), ": opened long limit on: ", symbol, " price: ", stoplimit)

            SpacerEnd()

            if r is None:
                return None
            if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
                break
        return r


    def _RawCancelOrder(self, order_number):
        # Create the request
        request = {
            "action": TRADE_ACTION_REMOVE,
            "order": order_number,
            "comment": "Order Removed"
        }
        # Send order to MT5
        order_result = order_send(request)
        return order_result


    def CancelOrders(self, symbol):
        SpacerStart()
        cancel = False
        orders = orders_get()
        limit_orders = [order for order in orders if
                        order.type == ORDER_TYPE_BUY_LIMIT or order.type == ORDER_TYPE_SELL_LIMIT]
        for order in limit_orders:
            if order.symbol == symbol:
                cancel = True
                self._RawCancelOrder(order.ticket)
                print(colorama.Fore.BLUE + str(self.log), ": order have been just cancelled on: ", symbol)

        if not cancel:
            print(str(self.log), ": there is no orders to cancel")
        SpacerEnd()
    def Disconnect(self):
        shutdown()
