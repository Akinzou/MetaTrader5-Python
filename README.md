# Python Library for MetaTrader 5 Connection

![MetaTrader 5]
This Python library enables you to connect with the MetaTrader 5 trading platform and interact with its features using Python. It allows executing trading operations, fetching market data, receiving notifications, and more.

## Requirements

To use this library, you need:

Python 3.x
MetaTrader 5 trading platform installed
MetaTrader 5 Python API (MetaTrader5 module)
colorama

## Installation

To install the library, use `pip`:

```bash
pip install MetaTrader5
pip install PythonMetaTrader5
```
# Getting Started

Import the library in your Python script:

```
from MetaTrader5 import *
```

Initialize the MetaTrader 5 library by calling the initialize() function.

Create an instance of the Broker class by providing your MetaTrader 5 login credentials and server:

```
broker = Broker(log=your_mt5_login, password="your_mt5_password", server="your_mt5_server")
```
### After successful login, you can perform trading operations such as placing orders and managing positions.


## Available Functions:
### Placing Orders:

``Buy(symbol, volume, price=None, *, comment=None, ticket=None):`` Places a Buy market order or limit order if price is specified.

``BuySL(symbol, volume, sl, price=None, *, comment=None, ticket=None):`` Places a Buy market order or limit order with a Stop Loss (SL) price if price is specified.

``Sell(symbol, volume, price=None, *, comment=None, ticket=None):`` Places a Sell market order or limit order if price is specified.

``SellSL(symbol, volume, sl, price=None, *, comment=None, ticket=None):`` Places a Sell market order or limit order with a Stop Loss (SL) price if price is specified.

``BuyLimit(symbol, volume, stoplimit, price=None, comment=None, ticket=None):`` Places a Buy limit order with the specified stoplimit price.

``SellLimit(symbol, volume, stoplimit, price=None, comment=None, ticket=None):`` Places a Sell limit order with the specified stoplimit price.


### Managing Positions:
``Close(symbol, *, comment=None, ticket=None):`` Closes all positions for the specified symbol or a specific position indicated by ticket.

``CancelOrders(symbol):`` Cancels all pending orders for the specified symbol.


### Miscellaneous:
``Disconnect():`` Closes the connection to the MetaTrader 5 trading platform.


## Example Usage:
```
from MetaTrader5 import *

# Initialize the MetaTrader 5 library
initialize()

# Create a broker instance and log in
broker = Broker(log=your_mt5_login, password="your_mt5_password", server="your_mt5_server")

# Place a Buy market order for 0.1 lot of EURUSD
broker.Buy("EURUSD", 0.1)

# Place a limit order for gold (if price is lower than 1900 it will be execute immediately
broker.BuyLimit("XAUUSD", 0.01, 1900)

# Close all positions for EURUSD
broker.Close("EURUSD")

# Cancel all pending orders for EURUSD
broker.CancelOrders("EURUSD")

# Disconnect from the MetaTrader 5 platform
broker.Disconnect()
```


## Note:
It is important to have the MetaTrader 5 trading platform running and logged in with the provided credentials before using this library.
This library is provided "as is" without any warranty. Use it at your own risk.
Before using this library in a live trading environment, thoroughly test it on a demo account to ensure its correctness and reliability.
