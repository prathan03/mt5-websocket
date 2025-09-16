#!/usr/bin/env python3
"""Main script to run MT5 Bot with WebSocket and API servers"""

import asyncio
import threading
import time
import logging
from mt5_websocket_server import MT5WebSocketServer
from api_server import app
import uvicorn
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_api_server():
    """Run FastAPI server in a thread"""
    uvicorn.run(app, host=Config.API_HOST, port=Config.API_PORT)

def run_websocket_server():
    """Run WebSocket server"""
    server = MT5WebSocketServer(host=Config.WS_HOST, port=Config.WS_PORT)

    # Initialize MT5 (uses already logged in terminal)
    if server.initialize_mt5(Config.MT5_PATH):
        try:
            asyncio.run(server.start_server())
        except KeyboardInterrupt:
            logger.info("WebSocket server stopped by user")
        finally:
            server.stop()
    else:
        logger.error("Failed to initialize MT5. Please make sure MT5 terminal is running and logged in.")

def main():
    """Main function to run both servers"""
    print("""
╔═══════════════════════════════════════╗
║       MT5 Trading Bot Started         ║
╚═══════════════════════════════════════╝

Starting servers...
- API Server: http://localhost:8000
- WebSocket Server: ws://localhost:8765
- Web Client: Open websocket_client_example.html

Press Ctrl+C to stop
    """)

    # Start API server in a thread
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()

    # Run WebSocket server in main thread
    try:
        run_websocket_server()
    except KeyboardInterrupt:
        print("\n\nShutting down servers...")
        time.sleep(1)
        print("Goodbye!")

if __name__ == "__main__":
    main()