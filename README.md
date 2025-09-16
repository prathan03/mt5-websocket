# MT5 Trading Bot with WebSocket & MCP Server

สำหรับเชื่อมต่อ MetaTrader 5 (MT5) พร้อม WebSocket server สำหรับส่งข้อมูล tick แบบ real-time และ MCP server สำหรับ AI agent integration

## Features

- 🚀 **WebSocket Server** - ส่งข้อมูล tick แบบ real-time ทุก tick
- 🤖 **MCP Server** - สำหรับ AI agent integration
- 🌐 **REST API** - FastAPI สำหรับ trading operations
- 📊 **Real-time Data** - รับข้อมูล bid/ask/spread แบบ real-time
- 📈 **Trading Operations** - เปิด/ปิด/แก้ไข orders
- 💰 **Risk Management** - คำนวณ position size ตาม risk

## Installation

1. Clone repository:
```bash
git clone <your-repo>
cd MT5Bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Setup configuration:
```bash
cp .env.example .env
# แก้ไขไฟล์ .env ใส่ข้อมูล MT5 account
```

## Configuration (.env)

```env
# MT5 Credentials
MT5_LOGIN=YOUR_MT5_LOGIN
MT5_PASSWORD=YOUR_MT5_PASSWORD
MT5_SERVER=YOUR_BROKER_SERVER
MT5_PATH=/path/to/terminal64.exe  # Optional for Windows

# Server Settings
API_HOST=0.0.0.0
API_PORT=8000
WS_HOST=0.0.0.0
WS_PORT=8765
```

## Usage

### 1. WebSocket Server (Real-time Tick Data)

```bash
python mt5_websocket_server.py
```

WebSocket server จะทำงานที่ port 8765

#### WebSocket Client Example (JavaScript):

```javascript
const ws = new WebSocket('ws://localhost:8765');

// Subscribe to symbol
ws.send(JSON.stringify({
    type: 'subscribe',
    symbol: 'EURUSD'
}));

// Receive tick data
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'tick') {
        console.log('Tick:', data.data);
        // {symbol, bid, ask, last, volume, time, spread}
    }
};
```

### 2. REST API Server

```bash
python api_server.py
# หรือ
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000
```

API จะทำงานที่ http://localhost:8000

#### API Endpoints:

- `POST /connect` - เชื่อมต่อ MT5
- `GET /account` - ข้อมูล account
- `GET /symbols` - รายการ symbols
- `GET /tick/{symbol}` - ข้อมูล tick ปัจจุบัน
- `GET /rates/{symbol}` - ข้อมูล historical
- `GET /positions` - positions ที่เปิดอยู่
- `POST /order` - เปิด order ใหม่
- `DELETE /position/{ticket}` - ปิด position
- `PATCH /position` - แก้ไข SL/TP

#### API Example:

```python
import requests

# Connect to MT5
response = requests.post('http://localhost:8000/connect', json={
    'login': 123456,
    'password': 'your_password',
    'server': 'ICMarkets-Demo'
})

# Get tick data
tick = requests.get('http://localhost:8000/tick/EURUSD').json()
print(f"EURUSD: Bid={tick['bid']}, Ask={tick['ask']}")

# Place order
order = requests.post('http://localhost:8000/order', json={
    'symbol': 'EURUSD',
    'order_type': 'BUY',
    'volume': 0.01,
    'sl': 1.0800,
    'tp': 1.0900
}).json()
```

### 3. MCP Server (AI Agent Integration)

```bash
python mcp_server.py
```

MCP server ให้ AI agents เข้าถึง MT5 functions

#### MCP Tools Available:

- `connect_mt5` - เชื่อมต่อ MT5
- `get_account_info` - ข้อมูล account
- `get_tick` - ข้อมูล tick
- `get_rates` - ข้อมูล historical
- `place_order` - เปิด order
- `close_position` - ปิด position
- `analyze_market` - วิเคราะห์ตลาด
- `calculate_position_size` - คำนวณ lot size

## WebSocket Message Types

### Subscribe to Symbol
```json
{
    "type": "subscribe",
    "symbol": "EURUSD"
}
```

### Tick Data Response
```json
{
    "type": "tick",
    "data": {
        "symbol": "EURUSD",
        "bid": 1.08123,
        "ask": 1.08125,
        "last": 1.08124,
        "volume": 1000,
        "time": "2024-01-15T10:30:45",
        "spread": 0.2
    }
}
```

## Testing

เปิดไฟล์ `websocket_client_example.html` ใน browser เพื่อทดสอบ WebSocket connection และดู real-time tick data

## Project Structure

```
MT5Bot/
├── mt5_handler.py           # MT5 connection handler
├── mt5_websocket_server.py  # WebSocket server for tick data
├── api_server.py            # FastAPI REST API
├── mcp_server.py           # MCP server for AI agents
├── config.py               # Configuration loader
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── websocket_client_example.html  # Test client
└── README.md              # Documentation
```

## Requirements

- Python 3.8+
- MetaTrader 5 Terminal
- MT5 Account (Demo หรือ Live)

## Notes

- ต้องเปิด MT5 Terminal ก่อนรัน server
- สำหรับ Windows: ระบุ path ของ terminal64.exe ใน .env
- สำหรับ Mac/Linux: ติดตั้ง MT5 ผ่าน Wine
- WebSocket จะส่ง tick data ทุกครั้งที่มีการเปลี่ยนแปลง bid/ask

## Security

- อย่าเก็บ credentials ใน code
- ใช้ .env file และอย่า commit ขึ้น git
- ใช้ demo account สำหรับทดสอบ
- ตั้ง firewall rules สำหรับ production

## License

MIT