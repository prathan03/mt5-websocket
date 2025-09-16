from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import json
import logging
from datetime import datetime
from mt5_handler import MT5Handler
import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MT5 Trading API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global MT5 handler
mt5_handler = MT5Handler()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        # Remove from subscriptions
        for symbol in list(self.subscriptions.keys()):
            if websocket in self.subscriptions[symbol]:
                self.subscriptions[symbol].remove(websocket)
                if not self.subscriptions[symbol]:
                    del self.subscriptions[symbol]

    async def subscribe(self, websocket: WebSocket, symbol: str):
        if symbol not in self.subscriptions:
            self.subscriptions[symbol] = []
        if websocket not in self.subscriptions[symbol]:
            self.subscriptions[symbol].append(websocket)

    async def broadcast_tick(self, symbol: str, data: dict):
        if symbol in self.subscriptions:
            for connection in self.subscriptions[symbol]:
                try:
                    await connection.send_json(data)
                except:
                    pass

manager = ConnectionManager()

# Pydantic models
class ConnectRequest(BaseModel):
    path: Optional[str] = None

class OrderRequest(BaseModel):
    symbol: str
    order_type: str  # BUY or SELL
    volume: float
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: str = ""
    magic: int = 0

class ModifyPositionRequest(BaseModel):
    ticket: int
    sl: Optional[float] = None
    tp: Optional[float] = None

class PositionSizeRequest(BaseModel):
    balance: float
    risk_percentage: float
    stop_loss_pips: int
    symbol: str

# API Endpoints
@app.get("/")
async def root():
    return {"message": "MT5 Trading API", "status": "online"}

@app.post("/connect")
async def connect(request: ConnectRequest = None):
    """Connect to MT5 terminal (uses already logged in terminal)"""
    path = request.path if request else None
    success = mt5_handler.connect(path)
    if success:
        return {
            "status": "connected",
            "account": mt5_handler.get_account_info()
        }
    raise HTTPException(status_code=400, detail="Connection failed. Please make sure MT5 is running and logged in.")

@app.post("/disconnect")
async def disconnect():
    """Disconnect from MT5"""
    mt5_handler.disconnect()
    return {"status": "disconnected"}

@app.get("/account")
async def get_account():
    """Get account information"""
    info = mt5_handler.get_account_info()
    if info:
        return info
    raise HTTPException(status_code=400, detail="Not connected to MT5")

@app.get("/symbols")
async def get_symbols(group: Optional[str] = None):
    """Get available trading symbols"""
    symbols = mt5_handler.get_symbols(group)
    return {"count": len(symbols), "symbols": symbols}

@app.get("/tick/{symbol}")
async def get_tick(symbol: str):
    """Get current tick data"""
    tick = mt5_handler.get_tick_data(symbol)
    if tick:
        return tick
    raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

@app.get("/rates/{symbol}")
async def get_rates(symbol: str, timeframe: str = "H1", count: int = 100):
    """Get historical rates"""
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

    tf = timeframe_map.get(timeframe, mt5.TIMEFRAME_H1)
    rates = mt5_handler.get_rates(symbol, tf, count)

    if not rates.empty:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "count": len(rates),
            "data": rates.to_dict('records')
        }
    raise HTTPException(status_code=404, detail="No data available")

@app.get("/positions")
async def get_positions():
    """Get all open positions"""
    positions = mt5_handler.get_positions()
    return {"count": len(positions), "positions": positions}

@app.get("/orders")
async def get_orders():
    """Get all pending orders"""
    orders = mt5_handler.get_orders()
    return {"count": len(orders), "orders": orders}

@app.post("/order")
async def place_order(request: OrderRequest):
    """Place a new order"""
    result = mt5_handler.place_order(
        request.symbol,
        request.order_type,
        request.volume,
        request.price,
        request.sl,
        request.tp,
        request.comment,
        request.magic
    )
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result.get("error", "Order failed"))

@app.delete("/position/{ticket}")
async def close_position(ticket: int):
    """Close a position"""
    result = mt5_handler.close_position(ticket)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result.get("error", "Failed to close position"))

@app.patch("/position")
async def modify_position(request: ModifyPositionRequest):
    """Modify position SL/TP"""
    result = mt5_handler.modify_position(request.ticket, request.sl, request.tp)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result.get("error", "Failed to modify position"))

@app.post("/calculate/position-size")
async def calculate_position_size(request: PositionSizeRequest):
    """Calculate optimal position size"""
    symbol_info = mt5.symbol_info(request.symbol)
    if not symbol_info:
        raise HTTPException(status_code=404, detail=f"Symbol {request.symbol} not found")

    risk_amount = request.balance * (request.risk_percentage / 100)
    pip_value = symbol_info.trade_tick_value
    position_size = risk_amount / (request.stop_loss_pips * pip_value)

    # Round to valid lot size
    lot_step = symbol_info.volume_step
    position_size = round(position_size / lot_step) * lot_step
    position_size = max(symbol_info.volume_min, min(position_size, symbol_info.volume_max))

    return {
        "position_size": position_size,
        "risk_amount": risk_amount,
        "pip_value": pip_value,
        "min_lot": symbol_info.volume_min,
        "max_lot": symbol_info.volume_max,
        "lot_step": symbol_info.volume_step
    }

# WebSocket endpoint for real-time tick data
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "subscribe":
                symbol = data.get("symbol")
                if symbol:
                    await manager.subscribe(websocket, symbol)
                    await websocket.send_json({
                        "type": "subscription",
                        "symbol": symbol,
                        "status": "subscribed"
                    })

                    # Start sending tick data
                    asyncio.create_task(send_tick_data(websocket, symbol))

            elif data.get("type") == "unsubscribe":
                symbol = data.get("symbol")
                if symbol and symbol in manager.subscriptions:
                    if websocket in manager.subscriptions[symbol]:
                        manager.subscriptions[symbol].remove(websocket)
                        await websocket.send_json({
                            "type": "subscription",
                            "symbol": symbol,
                            "status": "unsubscribed"
                        })

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def send_tick_data(websocket: WebSocket, symbol: str):
    """Send tick data to websocket client"""
    last_tick = None
    while websocket in manager.active_connections:
        try:
            if mt5_handler.connected:
                tick = mt5_handler.get_tick_data(symbol)
                if tick and (last_tick is None or
                           tick["bid"] != last_tick.get("bid") or
                           tick["ask"] != last_tick.get("ask")):
                    await manager.broadcast_tick(symbol, {
                        "type": "tick",
                        "data": tick
                    })
                    last_tick = tick
            await asyncio.sleep(0.01)  # Check every 10ms
        except:
            break

# Background task to keep connection alive
async def keep_alive():
    while True:
        if mt5_handler.connected:
            # Ping MT5 to keep connection alive
            mt5.symbol_info("EURUSD")
        await asyncio.sleep(30)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(keep_alive())

@app.on_event("shutdown")
async def shutdown_event():
    if mt5_handler.connected:
        mt5_handler.disconnect()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)