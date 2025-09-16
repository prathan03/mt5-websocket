#!/usr/bin/env python3
"""Test client for MT5 Bot - Testing WebSocket and API connections"""

import asyncio
import websockets
import json
import requests
import time
from datetime import datetime

# Configuration
API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8765"

def test_api():
    """Test REST API endpoints"""
    print("\n" + "="*50)
    print("Testing REST API")
    print("="*50)

    try:
        # Test connection
        print("\n1. Testing connection to MT5...")
        response = requests.post(f"{API_URL}/connect", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Connected: Account {data['account']['login']}")
            print(f"  Balance: {data['account']['balance']}")
            print(f"  Equity: {data['account']['equity']}")
        else:
            print(f"✗ Connection failed: {response.text}")
            return

        # Test getting symbols
        print("\n2. Getting available symbols...")
        response = requests.get(f"{API_URL}/symbols")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Found {data['count']} symbols")
            if data['symbols']:
                print(f"  First 5: {', '.join([s['name'] for s in data['symbols'][:5]])}")

        # Test getting tick data
        print("\n3. Getting tick data for EURUSD...")
        response = requests.get(f"{API_URL}/tick/EURUSD")
        if response.status_code == 200:
            tick = response.json()
            print(f"✓ EURUSD - Bid: {tick['bid']}, Ask: {tick['ask']}, Spread: {tick['spread']} pips")
        else:
            print(f"✗ Failed to get tick data: {response.text}")

        # Test getting positions
        print("\n4. Getting open positions...")
        response = requests.get(f"{API_URL}/positions")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Found {data['count']} open positions")
            for pos in data['positions']:
                print(f"  - {pos['symbol']}: {pos['type']} {pos['volume']} lots, Profit: {pos['profit']}")

        print("\n✓ API tests completed successfully!")

    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API server. Please make sure it's running.")
    except Exception as e:
        print(f"✗ Error: {str(e)}")

async def test_websocket():
    """Test WebSocket connection and tick data"""
    print("\n" + "="*50)
    print("Testing WebSocket Connection")
    print("="*50)

    try:
        async with websockets.connect(WS_URL) as websocket:
            print("\n✓ Connected to WebSocket server")

            # Wait for connection message
            message = await websocket.recv()
            data = json.loads(message)
            print(f"  Server: {data.get('message', 'Connected')}")

            # Subscribe to EURUSD
            print("\nSubscribing to EURUSD...")
            await websocket.send(json.dumps({
                "type": "subscribe",
                "symbol": "EURUSD"
            }))

            # Receive messages for 10 seconds
            print("\nReceiving tick data for 10 seconds...")
            print("-" * 40)

            start_time = time.time()
            tick_count = 0

            while time.time() - start_time < 10:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)

                    if data['type'] == 'tick':
                        tick_count += 1
                        tick_data = data['data']
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{timestamp}] {tick_data['symbol']}: "
                              f"Bid={tick_data['bid']:.5f}, "
                              f"Ask={tick_data['ask']:.5f}, "
                              f"Spread={tick_data['spread']:.1f}")

                    elif data['type'] == 'subscription':
                        print(f"  Subscription status: {data['status']}")

                except asyncio.TimeoutError:
                    continue

            print("-" * 40)
            print(f"\n✓ Received {tick_count} ticks in 10 seconds")

            # Unsubscribe
            print("\nUnsubscribing from EURUSD...")
            await websocket.send(json.dumps({
                "type": "unsubscribe",
                "symbol": "EURUSD"
            }))

            # Wait for unsubscribe confirmation
            message = await websocket.recv()
            data = json.loads(message)
            if data['type'] == 'subscription':
                print(f"  {data['status']}")

            print("\n✓ WebSocket tests completed successfully!")

    except ConnectionRefusedError:
        print("✗ Cannot connect to WebSocket server. Please make sure it's running.")
    except Exception as e:
        print(f"✗ Error: {str(e)}")

async def test_mcp_server():
    """Test MCP server via JSON-RPC"""
    print("\n" + "="*50)
    print("Testing MCP Server (JSON-RPC)")
    print("="*50)

    # Example of how to communicate with MCP server
    example_requests = [
        {
            "jsonrpc": "2.0",
            "method": "connect_mt5",
            "params": {},
            "id": 1
        },
        {
            "jsonrpc": "2.0",
            "method": "get_account_info",
            "params": {},
            "id": 2
        },
        {
            "jsonrpc": "2.0",
            "method": "get_tick",
            "params": {"symbol": "EURUSD"},
            "id": 3
        }
    ]

    print("\nMCP Server test requires manual JSON-RPC communication.")
    print("Example requests:")
    for req in example_requests:
        print(f"\n{json.dumps(req, indent=2)}")

def main():
    """Run all tests"""
    print("\n" + "="*50)
    print("MT5 Bot Test Suite")
    print("="*50)
    print("\nMake sure the following are running:")
    print("1. MT5 Terminal (logged in)")
    print("2. API Server (python api_server.py)")
    print("3. WebSocket Server (python mt5_websocket_server.py)")

    input("\nPress Enter to start tests...")

    # Test API
    test_api()

    # Test WebSocket
    print("\nStarting WebSocket test...")
    asyncio.run(test_websocket())

    # MCP Server info
    test_mcp_server()

    print("\n" + "="*50)
    print("All tests completed!")
    print("="*50)

if __name__ == "__main__":
    main()