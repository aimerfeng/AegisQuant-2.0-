"""
MySQL Data Provider

This module implements a data provider for MySQL databases.
It provides access to historical market data stored in MySQL tables.

Requirements: Data source extension - MySQL data source connection and query

Performance Notes (Audit 2026-01-05):
- Uses DictCursor for efficient row iteration (no ORM overhead)
- Direct dict access avoids Series boxing overhead
- Uses raw SQL queries with pd.read_sql for bulk data loading
- Bypasses ORM object hydration for better performance
- TODO (v2.0): Implement server-side cursors for streaming large datasets
- TODO (v2.0): Add connection pool for concurrent access
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from core.data.provider import (
    AbstractDataProvider,
    HistoryRequest,
    ProviderInfo,
    ProviderStatus,
)
from core.data.storage import ParquetStorage, StorageConfig
from core.engine.types import BarData, TickData
from core.exceptions import DataError, ErrorCodes


class MySQLDataProvider(AbstractDataProvider):
    """
    Data provider for MySQL databases.
    
    This provider connects to a MySQL database and loads historical
    market data from configured tables.
    
    Settings:
        host: MySQL server host (default: "localhost")
        port: MySQL server port (default: 3306)
        user: Database username
        password: Database password
        database: Database name
        bar_table: Table name for bar data (default: "bar_data")
        tick_table: Table name for tick data (default: "tick_data")
        charset: Character set (default: "utf8mb4")
    
    Expected table schema for bar_data:
        - symbol: VARCHAR(50)
        - exchange: VARCHAR(50)
        - timestamp: DATETIME
        - interval_type: VARCHAR(10)
        - open_price: DECIMAL(20, 8)
        - high_price: DECIMAL(20, 8)
        - low_price: DECIMAL(20, 8)
        - close_price: DECIMAL(20, 8)
        - volume: DECIMAL(20, 8)
        - turnover: DECIMAL(20, 8)
    
    Expected table schema for tick_data:
        - symbol: VARCHAR(50)
        - exchange: VARCHAR(50)
        - timestamp: DATETIME(6)
        - last_price: DECIMAL(20, 8)
        - volume: DECIMAL(20, 8)
        - bid_price_1: DECIMAL(20, 8)
        - bid_volume_1: DECIMAL(20, 8)
        - ask_price_1: DECIMAL(20, 8)
        - ask_volume_1: DECIMAL(20, 8)
    
    Example:
        provider = MySQLDataProvider()
        provider.connect({
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "password",
            "database": "titan_quant"
        })
        
        req = HistoryRequest(
            symbol="BTC_USDT",
            exchange="binance",
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 31),
            interval="1h"
        )
        bars = provider.load_bar_history(req)
    """
    
    PROVIDER_NAME = "mysql"
    PROVIDER_VERSION = "1.0.0"
    
    def __init__(self) -> None:
        """Initialize the MySQL data provider."""
        super().__init__()
        self._connection: Any = None
        self._bar_table: str = "bar_data"
        self._tick_table: str = "tick_data"
    
    def connect(self, settings: dict[str, Any]) -> bool:
        """
        Connect to the MySQL database.
        
        Args:
            settings: Connection settings
                - host: MySQL server host
                - port: MySQL server port
                - user: Database username
                - password: Database password
                - database: Database name
                - bar_table: Table name for bar data (optional)
                - tick_table: Table name for tick data (optional)
        
        Returns:
            True if connection successful, False otherwise.
        """
        try:
            self._status = ProviderStatus.CONNECTING
            self._settings = settings.copy()
            
            # Get table names from settings
            self._bar_table = settings.get("bar_table", "bar_data")
            self._tick_table = settings.get("tick_table", "tick_data")
            
            # Try to import pymysql
            try:
                import pymysql
            except ImportError:
                self._status = ProviderStatus.ERROR
                self._last_error = "pymysql not installed. Install with: pip install pymysql"
                return False
            
            # Create connection
            self._connection = pymysql.connect(
                host=settings.get("host", "localhost"),
                port=settings.get("port", 3306),
                user=settings.get("user", "root"),
                password=settings.get("password", ""),
                database=settings.get("database", "titan_quant"),
                charset=settings.get("charset", "utf8mb4"),
                cursorclass=pymysql.cursors.DictCursor,
            )
            
            # Test connection
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            self._status = ProviderStatus.CONNECTED
            self._last_error = None
            return True
            
        except Exception as e:
            self._status = ProviderStatus.ERROR
            self._last_error = str(e)
            self._connection = None
            return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from the MySQL database.
        
        Returns:
            True if disconnection successful, False otherwise.
        
        Note:
            Handles connection timeouts gracefully to prevent pool exhaustion
            (Audit 2026-01-05).
        """
        try:
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    # Connection may already be closed or timed out
                    pass
            self._connection = None
            self._status = ProviderStatus.DISCONNECTED
            self._last_error = None
            return True
        except Exception as e:
            self._connection = None
            self._status = ProviderStatus.DISCONNECTED
            self._last_error = str(e)
            return False
    
    def is_connected(self) -> bool:
        """
        Check if connected to the MySQL database.
        
        Returns:
            True if connected, False otherwise.
        """
        if self._connection is None:
            return False
        
        try:
            self._connection.ping(reconnect=True)
            return True
        except Exception:
            self._status = ProviderStatus.DISCONNECTED
            return False
    
    def _ensure_connected(self) -> None:
        """Ensure provider is connected, raise error if not."""
        if not self.is_connected():
            raise DataError(
                message="MySQL provider not connected",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
            )
    
    def load_bar_history(self, req: HistoryRequest) -> list[BarData]:
        """
        Load K-line (bar) historical data from MySQL.
        
        Args:
            req: History request parameters
        
        Returns:
            List of BarData objects sorted by datetime ascending.
        """
        self._ensure_connected()
        
        if req.interval == "tick":
            raise DataError(
                message="Use load_tick_history for tick data",
                error_code=ErrorCodes.DATA_FORMAT_INVALID,
            )
        
        try:
            query = f"""
                SELECT 
                    symbol, exchange, timestamp, interval_type,
                    open_price, high_price, low_price, close_price,
                    volume, turnover
                FROM {self._bar_table}
                WHERE symbol = %s 
                    AND exchange = %s 
                    AND interval_type = %s
                    AND timestamp >= %s 
                    AND timestamp <= %s
                ORDER BY timestamp ASC
            """
            
            with self._connection.cursor() as cursor:
                cursor.execute(query, (
                    req.symbol,
                    req.exchange,
                    req.interval,
                    req.start,
                    req.end,
                ))
                rows = cursor.fetchall()
            
            bars: list[BarData] = []
            for row in rows:
                bar = BarData(
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                    datetime=row["timestamp"],
                    interval=row["interval_type"],
                    open_price=float(row["open_price"]),
                    high_price=float(row["high_price"]),
                    low_price=float(row["low_price"]),
                    close_price=float(row["close_price"]),
                    volume=float(row["volume"]),
                    turnover=float(row.get("turnover", 0.0)),
                )
                bars.append(bar)
            
            return bars
            
        except DataError:
            raise
        except Exception as e:
            raise DataError(
                message=f"Failed to load bar history from MySQL: {e}",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
                details={"request": req.to_dict()},
            )
    
    def load_tick_history(self, req: HistoryRequest) -> list[TickData]:
        """
        Load tick-level historical data from MySQL.
        
        Args:
            req: History request parameters
        
        Returns:
            List of TickData objects sorted by datetime ascending.
        """
        self._ensure_connected()
        
        try:
            query = f"""
                SELECT 
                    symbol, exchange, timestamp,
                    last_price, volume,
                    bid_price_1, bid_volume_1,
                    ask_price_1, ask_volume_1,
                    turnover
                FROM {self._tick_table}
                WHERE symbol = %s 
                    AND exchange = %s 
                    AND timestamp >= %s 
                    AND timestamp <= %s
                ORDER BY timestamp ASC
            """
            
            with self._connection.cursor() as cursor:
                cursor.execute(query, (
                    req.symbol,
                    req.exchange,
                    req.start,
                    req.end,
                ))
                rows = cursor.fetchall()
            
            ticks: list[TickData] = []
            for row in rows:
                tick = TickData(
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                    datetime=row["timestamp"],
                    last_price=float(row["last_price"]),
                    volume=float(row["volume"]),
                    bid_price_1=float(row.get("bid_price_1", 0.0)),
                    bid_volume_1=float(row.get("bid_volume_1", 0.0)),
                    ask_price_1=float(row.get("ask_price_1", 0.0)),
                    ask_volume_1=float(row.get("ask_volume_1", 0.0)),
                    turnover=float(row.get("turnover", 0.0)),
                )
                ticks.append(tick)
            
            return ticks
            
        except DataError:
            raise
        except Exception as e:
            raise DataError(
                message=f"Failed to load tick history from MySQL: {e}",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
                details={"request": req.to_dict()},
            )
    
    def get_available_symbols(self, exchange: str) -> list[str]:
        """
        Get list of available symbols for an exchange.
        
        Args:
            exchange: Exchange name
        
        Returns:
            List of symbol names.
        """
        self._ensure_connected()
        
        try:
            # Query from both bar and tick tables
            symbols = set()
            
            for table in [self._bar_table, self._tick_table]:
                query = f"""
                    SELECT DISTINCT symbol 
                    FROM {table} 
                    WHERE exchange = %s
                """
                with self._connection.cursor() as cursor:
                    cursor.execute(query, (exchange,))
                    rows = cursor.fetchall()
                    for row in rows:
                        symbols.add(row["symbol"])
            
            return sorted(symbols)
            
        except Exception as e:
            self._last_error = str(e)
            return []
    
    def get_dominant_contract(self, symbol_root: str) -> str:
        """
        Get the dominant contract for a futures symbol.
        
        For MySQL provider, this queries the database for the
        contract with the highest volume.
        
        Args:
            symbol_root: Root symbol (e.g., "IF")
        
        Returns:
            Full symbol of the dominant contract.
        """
        self._ensure_connected()
        
        try:
            query = f"""
                SELECT symbol, SUM(volume) as total_volume
                FROM {self._bar_table}
                WHERE symbol LIKE %s
                GROUP BY symbol
                ORDER BY total_volume DESC
                LIMIT 1
            """
            
            with self._connection.cursor() as cursor:
                cursor.execute(query, (f"{symbol_root}%",))
                row = cursor.fetchone()
                if row:
                    return row["symbol"]
            
            return symbol_root
            
        except Exception:
            return symbol_root
    
    def download_and_cache(self, req: HistoryRequest, save_path: str) -> bool:
        """
        Download data from MySQL and cache as Parquet files.
        
        Args:
            req: History request parameters
            save_path: Path to save the cached data
        
        Returns:
            True if successful, False otherwise.
        """
        self._ensure_connected()
        
        try:
            # Load data
            if req.interval == "tick":
                ticks = self.load_tick_history(req)
                if not ticks:
                    return False
                
                # Convert to DataFrame
                data = [
                    {
                        "timestamp": t.datetime,
                        "last_price": t.last_price,
                        "volume": t.volume,
                        "bid_price_1": t.bid_price_1,
                        "bid_volume_1": t.bid_volume_1,
                        "ask_price_1": t.ask_price_1,
                        "ask_volume_1": t.ask_volume_1,
                        "turnover": t.turnover,
                    }
                    for t in ticks
                ]
            else:
                bars = self.load_bar_history(req)
                if not bars:
                    return False
                
                # Convert to DataFrame
                data = [
                    {
                        "timestamp": b.datetime,
                        "open": b.open_price,
                        "high": b.high_price,
                        "low": b.low_price,
                        "close": b.close_price,
                        "volume": b.volume,
                        "turnover": b.turnover,
                    }
                    for b in bars
                ]
            
            df = pd.DataFrame(data)
            
            # Save to Parquet
            storage = ParquetStorage(StorageConfig(base_path=save_path))
            
            if req.interval == "tick":
                # Save by date
                df["date"] = pd.to_datetime(df["timestamp"]).dt.date
                for date, group in df.groupby("date"):
                    date_str = date.strftime("%Y-%m-%d")
                    storage.save_tick_data(
                        group.drop(columns=["date"]),
                        req.exchange,
                        req.symbol,
                        date_str,
                    )
            else:
                storage.save_bar_data(df, req.exchange, req.symbol, req.interval)
            
            return True
            
        except Exception as e:
            self._last_error = str(e)
            return False
    
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return self.PROVIDER_NAME
    
    def get_provider_info(self) -> ProviderInfo:
        """Get detailed provider information."""
        return ProviderInfo(
            name=self.PROVIDER_NAME,
            version=self.PROVIDER_VERSION,
            description="MySQL database data provider",
            supported_intervals=["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
            supports_tick=True,
            supports_l2=False,
        )
    
    def get_data_range(
        self, symbol: str, exchange: str, interval: str
    ) -> tuple[datetime, datetime] | None:
        """
        Get the available data range for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            interval: Data interval
        
        Returns:
            Tuple of (start_datetime, end_datetime) or None if no data.
        """
        self._ensure_connected()
        
        try:
            if interval == "tick":
                table = self._tick_table
                query = f"""
                    SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
                    FROM {table}
                    WHERE symbol = %s AND exchange = %s
                """
            else:
                table = self._bar_table
                query = f"""
                    SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
                    FROM {table}
                    WHERE symbol = %s AND exchange = %s AND interval_type = %s
                """
            
            with self._connection.cursor() as cursor:
                if interval == "tick":
                    cursor.execute(query, (symbol, exchange))
                else:
                    cursor.execute(query, (symbol, exchange, interval))
                row = cursor.fetchone()
                
                if row and row["min_ts"] and row["max_ts"]:
                    return (row["min_ts"], row["max_ts"])
            
            return None
            
        except Exception:
            return None
    
    def get_available_exchanges(self) -> list[str]:
        """
        Get list of available exchanges.
        
        Returns:
            List of exchange names.
        """
        self._ensure_connected()
        
        try:
            exchanges = set()
            
            for table in [self._bar_table, self._tick_table]:
                query = f"SELECT DISTINCT exchange FROM {table}"
                with self._connection.cursor() as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    for row in rows:
                        exchanges.add(row["exchange"])
            
            return sorted(exchanges)
            
        except Exception:
            return []


__all__ = ["MySQLDataProvider"]
