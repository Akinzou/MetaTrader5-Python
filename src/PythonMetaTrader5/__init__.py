# internal order send
from MetaTrader5 import *

def _RawOrder(order_type, symbol, volume, price, sl=None, comment=None, ticket=None):
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


def _RawOrderLimit(order_type, symbol, volume, price, limit, comment=None, ticket=None):
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
def Close(symbol, *, comment=None, ticket=None):
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
                    r = _RawOrder(ORDER_TYPE_SELL, symbol, pos.volume, info.bid, comment, pos.ticket)
                else:
                    r = _RawOrder(ORDER_TYPE_BUY, symbol, pos.volume, info.ask, comment, pos.ticket)
                # check results
                if r is None:
                    return None
                if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
                    if r.retcode == TRADE_RETCODE_DONE:
                        done += 1
                    break

    if done > 0:
        if done == tried:
            return True
        else:
            return "Partially"
    return False


# Buy order
def Buy(symbol, volume, price=None, *, comment=None, ticket=None):
    # with direct call
    if price is not None:
        return _RawOrder(ORDER_TYPE_BUY, symbol, volume, price, comment, ticket)
    # no price, we try several times with current price
    for tries in range(10):
        info = symbol_info_tick(symbol)
        r = _RawOrder(ORDER_TYPE_BUY, symbol, volume, info.ask, comment, ticket)
        if r is None:
            return None
        if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
            break
    return r


def BuySL(symbol, volume, sl, price=None, *, comment=None, ticket=None):
    # with direct call
    if price is not None:
        return _RawOrder(ORDER_TYPE_BUY, symbol, volume, price, sl, comment, ticket)
    # no price, we try several times with current price
    for tries in range(10):
        info = symbol_info_tick(symbol)
        r = _RawOrder(ORDER_TYPE_BUY, symbol, volume, info.ask, sl, comment, ticket)
        if r is None:
            return None
        if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
            break
    return r


# Sell order
def Sell(symbol, volume, price=None, *, comment=None, ticket=None):
    # with direct call
    if price is not None:
        return _RawOrder(ORDER_TYPE_SELL, symbol, volume, price, comment, ticket)
    # no price, we try several times with current price
    for tries in range(10):
        info = symbol_info_tick(symbol)
        r = _RawOrder(ORDER_TYPE_SELL, symbol, volume, info.bid, comment, ticket)
        if r is None:
            return None
        if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
            break
    return r


def SellSL(symbol, volume, sl, price=None, *, comment=None, ticket=None):
    # with direct call
    if price is not None:
        return _RawOrder(ORDER_TYPE_SELL, symbol, volume, price, float(sl), comment, ticket)
    # no price, we try several times with current price
    for tries in range(10):
        info = symbol_info_tick(symbol)
        r = _RawOrder(ORDER_TYPE_SELL, symbol, volume, info.bid, float(sl), comment, ticket)
        if r is None:
            return None
        if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
            break
    return r


def SellLimit(symbol, volume, stoplimit, price=None, comment=None, ticket=None):
    # with direct call
    if price is not None:
        return _RawOrderLimit(ORDER_TYPE_SELL_LIMIT, symbol, float(volume), price, float(stoplimit), comment, ticket)
    # no price, we try several times with current price
    for tries in range(10):
        info = symbol_info_tick(symbol)
        if (info.bid >= stoplimit):
            r = _RawOrder(ORDER_TYPE_SELL, symbol, float(volume), info.bid, comment, ticket)
            print("Opened short on: ", symbol, "beacues of ask is > or = limit price")
        else:
            r = _RawOrderLimit(ORDER_TYPE_SELL_LIMIT, symbol, float(volume), info.bid, float(stoplimit), comment,
                               ticket)
            print("Opened short limit on: ", symbol, " price: ", stoplimit)
        if r is None:
            return None
        if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
            break
    return r


def BuyLimit(symbol, volume, stoplimit, price=None, comment=None, ticket=None):
    # with direct call
    if price is not None:
        return _RawOrderLimit(ORDER_TYPE_BUY_LIMIT, symbol, float(volume), price, float(stoplimit), comment, ticket)
    # no price, we try several times with current price
    for tries in range(10):
        info = symbol_info_tick(symbol)
        if (info.ask <= stoplimit):
            r = _RawOrder(ORDER_TYPE_BUY, symbol, float(volume), info.ask, comment, ticket)
            print("Opened long on: ", symbol, "beacues of ask is < or = limit price")
        else:
            r = _RawOrderLimit(ORDER_TYPE_BUY_LIMIT, symbol, float(volume), info.ask, float(stoplimit), comment, ticket)
            print("Opened long limit on: ", symbol, " price: ", stoplimit)
        if r is None:
            return None
        if r.retcode != TRADE_RETCODE_REQUOTE and r.retcode != TRADE_RETCODE_PRICE_OFF:
            break
    return r


def _RawCancelOrder(order_number):
    # Create the request
    request = {
        "action": TRADE_ACTION_REMOVE,
        "order": order_number,
        "comment": "Order Removed"
    }
    # Send order to MT5
    order_result = order_send(request)
    return order_result


def CancelOrders(symbol):
    cancel = False
    orders = orders_get()
    limit_orders = [order for order in orders if
                    order.type == ORDER_TYPE_BUY_LIMIT or order.type == ORDER_TYPE_SELL_LIMIT]
    for order in limit_orders:
        if order.symbol == symbol:
            cancel = True
            _RawCancelOrder(order.ticket)
            print("Order have been just cancelled on: ", symbol)
    if not cancel:
        print("There is no orders to cancel")
