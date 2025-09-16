import os

class Config:
    # MT5 Settings (optional path for Windows)
    MT5_PATH = os.getenv('MT5_PATH', None)

    # API Server Settings
    API_HOST = os.getenv('API_HOST', '0.0.0.0')
    API_PORT = int(os.getenv('API_PORT', '8000'))

    # WebSocket Settings
    WS_HOST = os.getenv('WS_HOST', '0.0.0.0')
    WS_PORT = int(os.getenv('WS_PORT', '8765'))

    # MCP Settings
    MCP_NAME = os.getenv('MCP_NAME', 'mt5-trading-bot')

    # Trading Settings
    DEFAULT_MAGIC_NUMBER = int(os.getenv('DEFAULT_MAGIC_NUMBER', '12345'))
    DEFAULT_DEVIATION = int(os.getenv('DEFAULT_DEVIATION', '10'))
    MAX_POSITIONS = int(os.getenv('MAX_POSITIONS', '10'))
    RISK_PERCENTAGE = float(os.getenv('RISK_PERCENTAGE', '2.0'))

    # Symbols to monitor (comma-separated)
    MONITOR_SYMBOLS = os.getenv('MONITOR_SYMBOLS', 'EURUSD,GBPUSD,USDJPY,GOLD').split(',')

    @classmethod
    def validate(cls):
        """Validate configuration"""
        # No validation needed for MT5 connection
        # as we use the already logged in terminal
        return True