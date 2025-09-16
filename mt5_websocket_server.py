import asyncio
import json
import websockets
import MetaTrader5 as mt5
from datetime import datetime
from typing import Dict, List, Set
import logging
from dataclasses import dataclass, asdict
import threading
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TickData:
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    time: str
    spread: float

class MT5WebSocketServer:
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.subscribed_symbols: Dict[str, Set[websockets.WebSocketServerProtocol]] = {}
        self.running = False
        self.mt5_connected = False

    def initialize_mt5(self, path=None):
        """Initialize MT5 connection (uses already logged in terminal)"""
        if path:
            if not mt5.initialize(path):
                logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                return False
        else:
            if not mt5.initialize():
                logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                return False

        account_info = mt5.account_info()
        if account_info is None:
            logger.error("No account connected in MT5 terminal. Please login to MT5 first.")
            mt5.shutdown()
            return False

        self.mt5_connected = True
        logger.info(f"MT5 connected successfully - Account: {account_info.login}")
        return True

    async def register_client(self, websocket):
        """Register new WebSocket client"""
        self.clients.add(websocket)
        logger.info(f"Client {websocket.remote_address} connected")

        await websocket.send(json.dumps({
            "type": "connection",
            "status": "connected",
            "message": "Connected to MT5 WebSocket Server"
        }))

    async def unregister_client(self, websocket):
        """Unregister WebSocket client"""
        self.clients.discard(websocket)

        for symbol in list(self.subscribed_symbols.keys()):
            self.subscribed_symbols[symbol].discard(websocket)
            if not self.subscribed_symbols[symbol]:
                del self.subscribed_symbols[symbol]

        logger.info(f"Client {websocket.remote_address} disconnected")

    async def subscribe_symbol(self, websocket, symbol):
        """Subscribe client to symbol tick data"""
        if symbol not in self.subscribed_symbols:
            self.subscribed_symbols[symbol] = set()

        self.subscribed_symbols[symbol].add(websocket)

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Symbol {symbol} not found"
            }))
            return False

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Failed to select symbol {symbol}"
                }))
                return False

        await websocket.send(json.dumps({
            "type": "subscription",
            "symbol": symbol,
            "status": "subscribed"
        }))

        logger.info(f"Client {websocket.remote_address} subscribed to {symbol}")
        return True

    async def unsubscribe_symbol(self, websocket, symbol):
        """Unsubscribe client from symbol"""
        if symbol in self.subscribed_symbols:
            self.subscribed_symbols[symbol].discard(websocket)
            if not self.subscribed_symbols[symbol]:
                del self.subscribed_symbols[symbol]

        await websocket.send(json.dumps({
            "type": "subscription",
            "symbol": symbol,
            "status": "unsubscribed"
        }))

    def get_tick_data(self, symbol) -> TickData:
        """Get current tick data for symbol"""
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            return TickData(
                symbol=symbol,
                bid=tick.bid,
                ask=tick.ask,
                last=tick.last,
                volume=tick.volume,
                time=datetime.fromtimestamp(tick.time).isoformat(),
                spread=round((tick.ask - tick.bid) * 10000, 2)  # Spread in pips
            )
        return None

    async def broadcast_tick(self, symbol, tick_data):
        """Broadcast tick data to subscribed clients"""
        if symbol in self.subscribed_symbols:
            message = json.dumps({
                "type": "tick",
                "data": asdict(tick_data)
            })

            disconnected = set()
            for client in self.subscribed_symbols[symbol]:
                try:
                    await client.send(message)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(client)

            for client in disconnected:
                await self.unregister_client(client)

    def tick_collector(self):
        """Background thread to collect and broadcast ticks"""
        last_ticks = {}

        while self.running:
            if not self.mt5_connected:
                time.sleep(1)
                continue

            for symbol in list(self.subscribed_symbols.keys()):
                if not self.subscribed_symbols[symbol]:
                    continue

                tick_data = self.get_tick_data(symbol)
                if tick_data:
                    last_tick = last_ticks.get(symbol)

                    if last_tick is None or (
                        last_tick.bid != tick_data.bid or
                        last_tick.ask != tick_data.ask
                    ):
                        last_ticks[symbol] = tick_data
                        asyncio.run_coroutine_threadsafe(
                            self.broadcast_tick(symbol, tick_data),
                            self.loop
                        )

            time.sleep(0.01)  # Check for ticks every 10ms

    async def handle_message(self, websocket, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'subscribe':
                symbol = data.get('symbol')
                if symbol:
                    await self.subscribe_symbol(websocket, symbol)

            elif msg_type == 'unsubscribe':
                symbol = data.get('symbol')
                if symbol:
                    await self.unsubscribe_symbol(websocket, symbol)

            elif msg_type == 'ping':
                await websocket.send(json.dumps({"type": "pong"}))

            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                }))

        except json.JSONDecodeError:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid JSON message"
            }))

    async def handle_client(self, websocket, path):
        """Handle WebSocket client connection"""
        await self.register_client(websocket)

        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister_client(websocket)

    async def start_server(self):
        """Start WebSocket server"""
        self.running = True
        self.loop = asyncio.get_event_loop()

        tick_thread = threading.Thread(target=self.tick_collector, daemon=True)
        tick_thread.start()

        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")

        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # Run forever

    def stop(self):
        """Stop the server"""
        self.running = False
        if self.mt5_connected:
            mt5.shutdown()
            self.mt5_connected = False

if __name__ == "__main__":
    server = MT5WebSocketServer(host='0.0.0.0', port=8765)

    # Initialize MT5 (uses already logged in terminal)
    if server.initialize_mt5():
        try:
            asyncio.run(server.start_server())
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        finally:
            server.stop()
    else:
        logger.error("Failed to initialize MT5. Please make sure MT5 terminal is running and logged in.")