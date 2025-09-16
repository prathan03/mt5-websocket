import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MT5Handler:
    def __init__(self):
        self.connected = False
        self.account_info = None

    def connect(self, path: str = None) -> bool:
        """Connect to MT5 terminal (uses already logged in terminal)"""
        try:
            if path:
                if not mt5.initialize(path):
                    logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                    return False
            else:
                if not mt5.initialize():
                    logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                    return False

            self.account_info = mt5.account_info()
            if self.account_info is None:
                logger.error("No account connected in MT5 terminal. Please login to MT5 first.")
                mt5.shutdown()
                return False

            self.connected = True
            logger.info(f"Connected to MT5 - Account: {self.account_info.login}, Server: {self.account_info.server}")
            return True

        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            return False

    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5")

    def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        if not self.connected:
            return None

        info = mt5.account_info()
        if info:
            return {
                "login": info.login,
                "server": info.server,
                "balance": info.balance,
                "equity": info.equity,
                "margin": info.margin,
                "margin_free": info.margin_free,
                "margin_level": info.margin_level,
                "profit": info.profit,
                "currency": info.currency,
                "leverage": info.leverage,
                "trade_mode": info.trade_mode,
                "limit_orders": info.limit_orders,
                "margin_so_mode": info.margin_so_mode,
                "trade_allowed": info.trade_allowed,
                "trade_expert": info.trade_expert
            }
        return None

    def get_symbols(self, group: str = None) -> List[Dict[str, Any]]:
        """Get available trading symbols"""
        if not self.connected:
            return []

        if group:
            symbols = mt5.symbols_get(group=group)
        else:
            symbols = mt5.symbols_get()

        result = []
        for symbol in symbols:
            result.append({
                "name": symbol.name,
                "path": symbol.path,
                "description": symbol.description,
                "point": symbol.point,
                "digits": symbol.digits,
                "spread": symbol.spread,
                "spread_float": symbol.spread_float,
                "tick_value": symbol.tick_value,
                "tick_size": symbol.tick_size,
                "contract_size": symbol.trade_contract_size,
                "volume_min": symbol.volume_min,
                "volume_max": symbol.volume_max,
                "volume_step": symbol.volume_step,
                "swap_long": symbol.swap_long,
                "swap_short": symbol.swap_short,
                "bid": symbol.bid,
                "ask": symbol.ask
            })
        return result

    def get_tick_data(self, symbol: str) -> Dict[str, Any]:
        """Get current tick data for symbol"""
        if not self.connected:
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick:
            return {
                "symbol": symbol,
                "time": datetime.fromtimestamp(tick.time).isoformat(),
                "bid": tick.bid,
                "ask": tick.ask,
                "last": tick.last,
                "volume": tick.volume,
                "volume_real": tick.volume_real,
                "spread": round((tick.ask - tick.bid) * 10000, 2)
            }
        return None

    def get_rates(self, symbol: str, timeframe: int, count: int = 100) -> pd.DataFrame:
        """Get historical rates data"""
        if not self.connected:
            return pd.DataFrame()

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        return pd.DataFrame()

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions"""
        if not self.connected:
            return []

        positions = mt5.positions_get()
        if positions is None:
            return []

        result = []
        for position in positions:
            result.append({
                "ticket": position.ticket,
                "time": datetime.fromtimestamp(position.time).isoformat(),
                "symbol": position.symbol,
                "type": "BUY" if position.type == mt5.POSITION_TYPE_BUY else "SELL",
                "volume": position.volume,
                "price_open": position.price_open,
                "price_current": position.price_current,
                "swap": position.swap,
                "profit": position.profit,
                "sl": position.sl,
                "tp": position.tp,
                "comment": position.comment,
                "magic": position.magic
            })
        return result

    def get_orders(self) -> List[Dict[str, Any]]:
        """Get all pending orders"""
        if not self.connected:
            return []

        orders = mt5.orders_get()
        if orders is None:
            return []

        result = []
        for order in orders:
            result.append({
                "ticket": order.ticket,
                "time_setup": datetime.fromtimestamp(order.time_setup).isoformat(),
                "symbol": order.symbol,
                "type": self._get_order_type_name(order.type),
                "volume": order.volume,
                "price_open": order.price_open,
                "price_current": order.price_current,
                "sl": order.sl,
                "tp": order.tp,
                "comment": order.comment,
                "magic": order.magic
            })
        return result

    def place_order(self, symbol: str, order_type: str, volume: float,
                    price: float = None, sl: float = None, tp: float = None,
                    comment: str = "", magic: int = 0) -> Dict[str, Any]:
        """Place a new order"""
        if not self.connected:
            return {"success": False, "error": "Not connected to MT5"}

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return {"success": False, "error": f"Symbol {symbol} not found"}

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                return {"success": False, "error": f"Failed to select symbol {symbol}"}

        point = symbol_info.point

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "magic": magic,
            "comment": comment,
            "deviation": 10,
        }

        if order_type.upper() == "BUY":
            request["type"] = mt5.ORDER_TYPE_BUY
            request["price"] = symbol_info.ask if price is None else price
        elif order_type.upper() == "SELL":
            request["type"] = mt5.ORDER_TYPE_SELL
            request["price"] = symbol_info.bid if price is None else price
        else:
            return {"success": False, "error": f"Invalid order type: {order_type}"}

        if sl is not None:
            request["sl"] = sl
        if tp is not None:
            request["tp"] = tp

        result = mt5.order_send(request)

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return {
                "success": True,
                "order": result.order,
                "deal": result.deal,
                "volume": result.volume,
                "price": result.price,
                "comment": result.comment
            }
        else:
            return {
                "success": False,
                "error": f"Order failed: {result.comment}",
                "retcode": result.retcode
            }

    def close_position(self, ticket: int) -> Dict[str, Any]:
        """Close an open position"""
        if not self.connected:
            return {"success": False, "error": "Not connected to MT5"}

        position = mt5.positions_get(ticket=ticket)
        if not position:
            return {"success": False, "error": f"Position {ticket} not found"}

        position = position[0]
        symbol_info = mt5.symbol_info(position.symbol)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": position.symbol,
            "volume": position.volume,
            "deviation": 10,
        }

        if position.type == mt5.POSITION_TYPE_BUY:
            request["type"] = mt5.ORDER_TYPE_SELL
            request["price"] = symbol_info.bid
        else:
            request["type"] = mt5.ORDER_TYPE_BUY
            request["price"] = symbol_info.ask

        result = mt5.order_send(request)

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return {
                "success": True,
                "order": result.order,
                "deal": result.deal,
                "volume": result.volume,
                "price": result.price
            }
        else:
            return {
                "success": False,
                "error": f"Failed to close position: {result.comment}",
                "retcode": result.retcode
            }

    def modify_position(self, ticket: int, sl: float = None, tp: float = None) -> Dict[str, Any]:
        """Modify stop loss and take profit of a position"""
        if not self.connected:
            return {"success": False, "error": "Not connected to MT5"}

        position = mt5.positions_get(ticket=ticket)
        if not position:
            return {"success": False, "error": f"Position {ticket} not found"}

        position = position[0]

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": position.symbol,
        }

        if sl is not None:
            request["sl"] = sl
        else:
            request["sl"] = position.sl

        if tp is not None:
            request["tp"] = tp
        else:
            request["tp"] = position.tp

        result = mt5.order_send(request)

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            return {"success": True, "message": "Position modified successfully"}
        else:
            return {
                "success": False,
                "error": f"Failed to modify position: {result.comment}",
                "retcode": result.retcode
            }

    def _get_order_type_name(self, order_type: int) -> str:
        """Convert order type number to string"""
        types = {
            mt5.ORDER_TYPE_BUY: "BUY",
            mt5.ORDER_TYPE_SELL: "SELL",
            mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
            mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
            mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
            mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP",
            mt5.ORDER_TYPE_BUY_STOP_LIMIT: "BUY_STOP_LIMIT",
            mt5.ORDER_TYPE_SELL_STOP_LIMIT: "SELL_STOP_LIMIT",
        }
        return types.get(order_type, "UNKNOWN")