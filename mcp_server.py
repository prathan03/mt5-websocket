#!/usr/bin/env python3
"""MCP Server for MT5 Trading Bot - AI Agent Integration"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from mcp import Server, Tool
from mcp.server.stdio import stdio_server
from mt5_handler import MT5Handler
import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MT5MCPServer:
    def __init__(self):
        self.server = Server("mt5-trading-bot")
        self.mt5_handler = MT5Handler()
        self.setup_tools()

    def setup_tools(self):
        """Setup MCP tools for MT5 operations"""

        @self.server.tool()
        async def connect_mt5(login: int, password: str, server: str, path: Optional[str] = None) -> Dict[str, Any]:
            """Connect to MT5 trading terminal"""
            success = self.mt5_handler.connect(login, password, server, path)
            if success:
                return {"status": "connected", "account": self.mt5_handler.get_account_info()}
            return {"status": "failed", "error": "Connection failed"}

        @self.server.tool()
        async def disconnect_mt5() -> Dict[str, Any]:
            """Disconnect from MT5 terminal"""
            self.mt5_handler.disconnect()
            return {"status": "disconnected"}

        @self.server.tool()
        async def get_account_info() -> Dict[str, Any]:
            """Get current account information"""
            info = self.mt5_handler.get_account_info()
            if info:
                return {"status": "success", "data": info}
            return {"status": "error", "message": "Not connected to MT5"}

        @self.server.tool()
        async def get_symbols(group: Optional[str] = None) -> Dict[str, Any]:
            """Get available trading symbols"""
            symbols = self.mt5_handler.get_symbols(group)
            return {"status": "success", "count": len(symbols), "symbols": symbols}

        @self.server.tool()
        async def get_tick(symbol: str) -> Dict[str, Any]:
            """Get current tick data for a symbol"""
            tick = self.mt5_handler.get_tick_data(symbol)
            if tick:
                return {"status": "success", "data": tick}
            return {"status": "error", "message": f"Failed to get tick for {symbol}"}

        @self.server.tool()
        async def get_rates(symbol: str, timeframe: str = "M1", count: int = 100) -> Dict[str, Any]:
            """Get historical rate data

            Timeframes: M1, M5, M15, M30, H1, H4, D1, W1, MN1
            """
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

        @self.server.tool()
        async def get_positions() -> Dict[str, Any]:
            """Get all open positions"""
            positions = self.mt5_handler.get_positions()
            return {
                "status": "success",
                "count": len(positions),
                "positions": positions
            }

        @self.server.tool()
        async def get_orders() -> Dict[str, Any]:
            """Get all pending orders"""
            orders = self.mt5_handler.get_orders()
            return {
                "status": "success",
                "count": len(orders),
                "orders": orders
            }

        @self.server.tool()
        async def place_order(
            symbol: str,
            order_type: str,
            volume: float,
            price: Optional[float] = None,
            sl: Optional[float] = None,
            tp: Optional[float] = None,
            comment: str = "",
            magic: int = 0
        ) -> Dict[str, Any]:
            """Place a new order

            order_type: BUY or SELL
            volume: Lot size (e.g., 0.01 for micro lot)
            """
            result = self.mt5_handler.place_order(
                symbol, order_type, volume, price, sl, tp, comment, magic
            )
            return result

        @self.server.tool()
        async def close_position(ticket: int) -> Dict[str, Any]:
            """Close an open position by ticket number"""
            result = self.mt5_handler.close_position(ticket)
            return result

        @self.server.tool()
        async def modify_position(
            ticket: int,
            sl: Optional[float] = None,
            tp: Optional[float] = None
        ) -> Dict[str, Any]:
            """Modify stop loss and/or take profit of a position"""
            result = self.mt5_handler.modify_position(ticket, sl, tp)
            return result

        @self.server.tool()
        async def analyze_market(symbol: str) -> Dict[str, Any]:
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

        @self.server.tool()
        async def calculate_position_size(
            balance: float,
            risk_percentage: float,
            stop_loss_pips: int,
            symbol: str
        ) -> Dict[str, Any]:
            """Calculate optimal position size based on risk management"""
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

    async def run(self):
        """Run the MCP server"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream)

if __name__ == "__main__":
    server = MT5MCPServer()
    asyncio.run(server.run())