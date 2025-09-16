#!/usr/bin/env python3
"""MCP Server for MT5 Trading Bot - Standalone version without MCP package"""

import asyncio
import json
import sys
from typing import Any, Dict, List, Optional
from mt5_handler import MT5Handler
import MetaTrader5 as mt5
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MT5MCPServer:
    """MCP-style server for MT5 operations via JSON-RPC over stdio"""

    def __init__(self):
        self.mt5_handler = MT5Handler()
        self.methods = {}
        self.setup_methods()

    def setup_methods(self):
        """Register available methods"""

        self.methods = {
            "connect_mt5": self.connect_mt5,
            "disconnect_mt5": self.disconnect_mt5,
            "get_account_info": self.get_account_info,
            "get_symbols": self.get_symbols,
            "get_tick": self.get_tick,
            "get_rates": self.get_rates,
            "get_positions": self.get_positions,
            "get_orders": self.get_orders,
            "place_order": self.place_order,
            "close_position": self.close_position,
            "modify_position": self.modify_position,
            "analyze_market": self.analyze_market,
            "calculate_position_size": self.calculate_position_size,
        }

    async def connect_mt5(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Connect to MT5 trading terminal (uses already logged in terminal)"""
        success = self.mt5_handler.connect(path)
        if success:
            return {"status": "connected", "account": self.mt5_handler.get_account_info()}
        return {"status": "failed", "error": "Connection failed. Please make sure MT5 is running and logged in."}

    async def disconnect_mt5(self) -> Dict[str, Any]:
        """Disconnect from MT5 terminal"""
        self.mt5_handler.disconnect()
        return {"status": "disconnected"}

    async def get_account_info(self) -> Dict[str, Any]:
        """Get current account information"""
        info = self.mt5_handler.get_account_info()
        if info:
            return {"status": "success", "data": info}
        return {"status": "error", "message": "Not connected to MT5"}

    async def get_symbols(self, group: Optional[str] = None) -> Dict[str, Any]:
        """Get available trading symbols"""
        symbols = self.mt5_handler.get_symbols(group)
        return {"status": "success", "count": len(symbols), "symbols": symbols}

    async def get_tick(self, symbol: str) -> Dict[str, Any]:
        """Get current tick data for a symbol"""
        tick = self.mt5_handler.get_tick_data(symbol)
        if tick:
            return {"status": "success", "data": tick}
        return {"status": "error", "message": f"Failed to get tick for {symbol}"}

    async def get_rates(self, symbol: str, timeframe: str = "M1", count: int = 100) -> Dict[str, Any]:
        """Get historical rate data"""
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1
        }

        tf = timeframe_map.get(timeframe, mt5.TIMEFRAME_M1)
        rates = self.mt5_handler.get_rates(symbol, tf, count)

        if not rates.empty:
            return {
                "status": "success",
                "symbol": symbol,
                "timeframe": timeframe,
                "count": len(rates),
                "data": rates.to_dict('records')
            }
        return {"status": "error", "message": "No data available"}

    async def get_positions(self) -> Dict[str, Any]:
        """Get all open positions"""
        positions = self.mt5_handler.get_positions()
        return {
            "status": "success",
            "count": len(positions),
            "positions": positions
        }

    async def get_orders(self) -> Dict[str, Any]:
        """Get all pending orders"""
        orders = self.mt5_handler.get_orders()
        return {
            "status": "success",
            "count": len(orders),
            "orders": orders
        }

    async def place_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
        magic: int = 0
    ) -> Dict[str, Any]:
        """Place a new order"""
        result = self.mt5_handler.place_order(
            symbol, order_type, volume, price, sl, tp, comment, magic
        )
        return result

    async def close_position(self, ticket: int) -> Dict[str, Any]:
        """Close an open position by ticket number"""
        result = self.mt5_handler.close_position(ticket)
        return result

    async def modify_position(
        self,
        ticket: int,
        sl: Optional[float] = None,
        tp: Optional[float] = None
    ) -> Dict[str, Any]:
        """Modify stop loss and/or take profit of a position"""
        result = self.mt5_handler.modify_position(ticket, sl, tp)
        return result

    async def analyze_market(self, symbol: str) -> Dict[str, Any]:
        """Analyze market conditions for a symbol"""
        tick = self.mt5_handler.get_tick_data(symbol)
        rates = self.mt5_handler.get_rates(symbol, mt5.TIMEFRAME_H1, 24)

        if tick and not rates.empty:
            analysis = {
                "symbol": symbol,
                "current_price": {
                    "bid": tick["bid"],
                    "ask": tick["ask"],
                    "spread": tick["spread"]
                },
                "24h_stats": {
                    "high": float(rates['high'].max()),
                    "low": float(rates['low'].min()),
                    "average": float(rates['close'].mean()),
                    "volatility": float(rates['close'].std())
                },
                "trend": self._calculate_trend(rates)
            }
            return {"status": "success", "analysis": analysis}
        return {"status": "error", "message": "Unable to analyze market"}

    async def calculate_position_size(
        self,
        balance: float,
        risk_percentage: float,
        stop_loss_pips: int,
        symbol: str
    ) -> Dict[str, Any]:
        """Calculate optimal position size based on risk management"""
        if not self.mt5_handler.connected:
            return {"status": "error", "message": "Not connected to MT5"}

        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return {"status": "error", "message": f"Symbol {symbol} not found"}

        risk_amount = balance * (risk_percentage / 100)
        pip_value = symbol_info.trade_tick_value
        position_size = risk_amount / (stop_loss_pips * pip_value)

        # Round to valid lot size
        lot_step = symbol_info.volume_step
        position_size = round(position_size / lot_step) * lot_step
        position_size = max(symbol_info.volume_min, min(position_size, symbol_info.volume_max))

        return {
            "status": "success",
            "position_size": position_size,
            "risk_amount": risk_amount,
            "pip_value": pip_value
        }

    def _calculate_trend(self, rates) -> str:
        """Calculate market trend from rate data"""
        if rates.empty:
            return "unknown"

        sma_short = rates['close'].tail(10).mean()
        sma_long = rates['close'].tail(20).mean()

        if sma_short > sma_long * 1.01:
            return "bullish"
        elif sma_short < sma_long * 0.99:
            return "bearish"
        else:
            return "neutral"

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle JSON-RPC request"""
        method = request.get("method")
        params = request.get("params", {})
        id = request.get("id")

        if method not in self.methods:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                },
                "id": id
            }

        try:
            result = await self.methods[method](**params)
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": id
            }
        except Exception as e:
            logger.error(f"Error executing {method}: {str(e)}")
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": str(e)
                },
                "id": id
            }

    async def run_stdio(self):
        """Run server using stdio for communication"""
        logger.info("MT5 MCP Server started (stdio mode)")

        # Send capabilities
        capabilities = {
            "name": "mt5-trading-bot",
            "version": "1.0.0",
            "methods": list(self.methods.keys())
        }
        print(json.dumps(capabilities))
        sys.stdout.flush()

        # Read requests from stdin
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                if not line:
                    break

                request = json.loads(line.strip())
                response = await self.handle_request(request)

                print(json.dumps(response))
                sys.stdout.flush()

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")

        self.mt5_handler.disconnect()

if __name__ == "__main__":
    server = MT5MCPServer()
    try:
        asyncio.run(server.run_stdio())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")