"""
MongoDB Data Provider

This module implements a data provider for MongoDB databases.
It provides access to historical market data stored in MongoDB collections.

Requirements: Data source extension - MongoDB data source connection and query
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


class MongoDBDataProvider(AbstractDataProvider):
    """
    Data provider for MongoDB databases.
    
    This provider connects to a MongoDB database and loads historical
    market data from configured collections.
    
    Settings:
        host: MongoDB server host (default: "localhost")
        port: MongoDB server port (default: 27017)
        username: Database username (optional)
        password: Database password (optional)
        database: Database name (default: "titan_quant")
        bar_collection: Collection name for bar data (default: "bar_data")
        tick_collection: Collection name for tick data (default: "tick_data")
        auth_source: Authentication database (default: "admin")
    
    Expected document schema for bar_data:
        {
            "symbol": "BTC_USDT",
            "exchange": "binance",
            "timestamp": ISODate("2024-01-01T00:00:00Z"),
            "interval": "1h",
            "open": 42000.0,
            "high": 42500.0,
            "low": 41800.0,
            "close": 42200.0,
            "volume": 1000.0,
            "turnover": 42000000.0
        }
    
    Expected document schema for tick_data:
        {
            "symbol": "BTC_USDT",
            "exchange": "binance",
            "timestamp": ISODate("2024-01-01T00:00:00.123Z"),
            "last_price": 42000.0,
            "volume": 1.5,
            "bid_price_1": 41999.0,
            "bid_volume_1": 10.0,
            "ask_price_1": 42001.0,
            "ask_volume_1": 8.0,
            "turnover": 63000.0
        }
    
    Example:
        provider = MongoDBDataProvider()
        provider.connect({
            "host": "localhost",
            "port": 27017,
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
    
    PROVIDER_NAME = "mongodb"
    PROVIDER_VERSION = "1.0.0"
    
    def __init__(self) -> None:
        """Initialize the MongoDB data provider."""
        super().__init__()
        self._client: Any = None
        self._db: Any = None
        self._bar_collection: str = "bar_data"
        self._tick_collection: str = "tick_data"
    
    def connect(self, settings: dict[str, Any]) -> bool:
        """
        Connect to the MongoDB database.
        
        Args:
            settings: Connection settings
                - host: MongoDB server host
                - port: MongoDB server port
                - username: Database username (optional)
                - password: Database password (optional)
                - database: Database name
                - bar_collection: Collection name for bar data (optional)
                - tick_collection: Collection name for tick data (optional)
                - auth_source: Authentication database (optional)
        
        Returns:
            True if connection successful, False otherwise.
        """
        try:
            self._status = ProviderStatus.CONNECTING
            self._settings = settings.copy()
            
            # Get collection names from settings
            self._bar_collection = settings.get("bar_collection", "bar_data")
            self._tick_collection = settings.get("tick_collection", "tick_data")
            
            # Try to import pymongo
            try:
                from pymongo import MongoClient
            except ImportError:
                self._status = ProviderStatus.ERROR
                self._last_error = "pymongo not installed. Install with: pip install pymongo"
                return False
            
            # Build connection URI
            host = settings.get("host", "localhost")
            port = settings.get("port", 27017)
            username = settings.get("username")
            password = settings.get("password")
            auth_source = settings.get("auth_source", "admin")
            
            if username and password:
                uri = f"mongodb://{username}:{password}@{host}:{port}/?authSource={auth_source}"
            else:
                uri = f"mongodb://{host}:{port}/"
            
            # Create client and connect
            self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            
            # Test connection
            self._client.admin.command("ping")
            
            # Get database
            database = settings.get("database", "titan_quant")
            self._db = self._client[database]
            
            self._status = ProviderStatus.CONNECTED
            self._last_error = None
            return True
            
        except Exception as e:
            self._status = ProviderStatus.ERROR
            self._last_error = str(e)
            self._client = None
            self._db = None
            return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from the MongoDB database.
        
        Returns:
            True if disconnection successful, False otherwise.
        """
        try:
            if self._client is not None:
                self._client.close()
            self._client = None
            self._db = None
            self._status = ProviderStatus.DISCONNECTED
            self._last_error = None
            return True
        except Exception as e:
            self._last_error = str(e)
            return False
    
    def is_connected(self) -> bool:
        """
        Check if connected to the MongoDB database.
        
        Returns:
            True if connected, False otherwise.
        """
        if self._client is None or self._db is None:
            return False
        
        try:
            self._client.admin.command("ping")
            return True
        except Exception:
            self._status = ProviderStatus.DISCONNECTED
            return False
    
    def _ensure_connected(self) -> None:
        """Ensure provider is connected, raise error if not."""
        if not self.is_connected():
            raise DataError(
                message="MongoDB provider not connected",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
            )
    
    def load_bar_history(self, req: HistoryRequest) -> list[BarData]:
        """
        Load K-line (bar) historical data from MongoDB.
        
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
            collection = self._db[self._bar_collection]
            
            query = {
                "symbol": req.symbol,
                "exchange": req.exchange,
                "interval": req.interval,
                "timestamp": {
                    "$gte": req.start,
                    "$lte": req.end,
                },
            }
            
            cursor = collection.find(query).sort("timestamp", 1)
            
            bars: list[BarData] = []
            for doc in cursor:
                bar = BarData(
                    symbol=doc["symbol"],
                    exchange=doc["exchange"],
                    datetime=doc["timestamp"],
                    interval=doc["interval"],
                    open_price=float(doc["open"]),
                    high_price=float(doc["high"]),
                    low_price=float(doc["low"]),
                    close_price=float(doc["close"]),
                    volume=float(doc["volume"]),
                    turnover=float(doc.get("turnover", 0.0)),
                )
                bars.append(bar)
            
            return bars
            
        except DataError:
            raise
        except Exception as e:
            raise DataError(
                message=f"Failed to load bar history from MongoDB: {e}",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
                details={"request": req.to_dict()},
            )
    
    def load_tick_history(self, req: HistoryRequest) -> list[TickData]:
        """
        Load tick-level historical data from MongoDB.
        
        Args:
            req: History request parameters
        
        Returns:
            List of TickData objects sorted by datetime ascending.
        """
        self._ensure_connected()
        
        try:
            collection = self._db[self._tick_collection]
            
            query = {
                "symbol": req.symbol,
                "exchange": req.exchange,
                "timestamp": {
                    "$gte": req.start,
                    "$lte": req.end,
                },
            }
            
            cursor = collection.find(query).sort("timestamp", 1)
            
            ticks: list[TickData] = []
            for doc in cursor:
                tick = TickData(
                    symbol=doc["symbol"],
                    exchange=doc["exchange"],
                    datetime=doc["timestamp"],
                    last_price=float(doc["last_price"]),
                    volume=float(doc["volume"]),
                    bid_price_1=float(doc.get("bid_price_1", 0.0)),
                    bid_volume_1=float(doc.get("bid_volume_1", 0.0)),
                    ask_price_1=float(doc.get("ask_price_1", 0.0)),
                    ask_volume_1=float(doc.get("ask_volume_1", 0.0)),
                    turnover=float(doc.get("turnover", 0.0)),
                )
                ticks.append(tick)
            
            return ticks
            
        except DataError:
            raise
        except Exception as e:
            raise DataError(
                message=f"Failed to load tick history from MongoDB: {e}",
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
            symbols = set()
            
            # Query from both bar and tick collections
            for coll_name in [self._bar_collection, self._tick_collection]:
                collection = self._db[coll_name]
                result = collection.distinct("symbol", {"exchange": exchange})
                symbols.update(result)
            
            return sorted(symbols)
            
        except Exception as e:
            self._last_error = str(e)
            return []
    
    def get_dominant_contract(self, symbol_root: str) -> str:
        """
        Get the dominant contract for a futures symbol.
        
        For MongoDB provider, this queries the database for the
        contract with the highest volume.
        
        Args:
            symbol_root: Root symbol (e.g., "IF")
        
        Returns:
            Full symbol of the dominant contract.
        """
        self._ensure_connected()
        
        try:
            import re
            collection = self._db[self._bar_collection]
            
            # Aggregate to find symbol with highest volume
            pipeline = [
                {"$match": {"symbol": {"$regex": f"^{re.escape(symbol_root)}"}}},
                {"$group": {"_id": "$symbol", "total_volume": {"$sum": "$volume"}}},
                {"$sort": {"total_volume": -1}},
                {"$limit": 1},
            ]
            
            result = list(collection.aggregate(pipeline))
            if result:
                return result[0]["_id"]
            
            return symbol_root
            
        except Exception:
            return symbol_root
    
    def download_and_cache(self, req: HistoryRequest, save_path: str) -> bool:
        """
        Download data from MongoDB and cache as Parquet files.
        
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
            description="MongoDB database data provider",
            supported_intervals=["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
            supports_tick=True,
            supports_l2=True,  # MongoDB can store L2 data in nested documents
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
                collection = self._db[self._tick_collection]
                query = {"symbol": symbol, "exchange": exchange}
            else:
                collection = self._db[self._bar_collection]
                query = {"symbol": symbol, "exchange": exchange, "interval": interval}
            
            # Get min timestamp
            min_doc = collection.find_one(query, sort=[("timestamp", 1)])
            if not min_doc:
                return None
            
            # Get max timestamp
            max_doc = collection.find_one(query, sort=[("timestamp", -1)])
            if not max_doc:
                return None
            
            return (min_doc["timestamp"], max_doc["timestamp"])
            
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
            
            for coll_name in [self._bar_collection, self._tick_collection]:
                collection = self._db[coll_name]
                result = collection.distinct("exchange")
                exchanges.update(result)
            
            return sorted(exchanges)
            
        except Exception:
            return []
    
    def create_indexes(self) -> bool:
        """
        Create recommended indexes for better query performance.
        
        Returns:
            True if indexes created successfully, False otherwise.
        """
        self._ensure_connected()
        
        try:
            # Bar data indexes
            bar_collection = self._db[self._bar_collection]
            bar_collection.create_index([
                ("symbol", 1),
                ("exchange", 1),
                ("interval", 1),
                ("timestamp", 1),
            ])
            
            # Tick data indexes
            tick_collection = self._db[self._tick_collection]
            tick_collection.create_index([
                ("symbol", 1),
                ("exchange", 1),
                ("timestamp", 1),
            ])
            
            return True
            
        except Exception as e:
            self._last_error = str(e)
            return False


__all__ = ["MongoDBDataProvider"]
