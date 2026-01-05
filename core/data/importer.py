"""
Data Importer Module

This module provides high-performance data import functionality for the
Titan-Quant system. It supports multiple file formats (CSV, Excel, Parquet)
and uses Pandas for data loading.

Requirements: 2.1 - Multi-format data import with automatic format detection
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from core.exceptions import DataError, ErrorCodes


class DataFormat(Enum):
    """Supported data file formats."""
    CSV = "csv"
    EXCEL = "excel"
    PARQUET = "parquet"
    UNKNOWN = "unknown"


class DataImporter:
    """
    High-performance data importer using Pandas.
    
    Supports automatic format detection and parsing of CSV, Excel, and Parquet files.
    
    Example:
        importer = DataImporter()
        df = importer.import_file("data.csv")
        # or with auto-detection
        df = importer.import_file("data.xlsx")
    """
    
    # File extension to format mapping
    EXTENSION_MAP: dict[str, DataFormat] = {
        ".csv": DataFormat.CSV,
        ".txt": DataFormat.CSV,  # Treat .txt as CSV
        ".xlsx": DataFormat.EXCEL,
        ".xls": DataFormat.EXCEL,
        ".xlsm": DataFormat.EXCEL,
        ".parquet": DataFormat.PARQUET,
        ".pq": DataFormat.PARQUET,
    }

    def __init__(self) -> None:
        """Initialize the DataImporter."""
        pass
    
    def detect_format(self, file_path: str | Path) -> DataFormat:
        """
        Detect the format of a data file.
        
        Uses a combination of file extension and magic bytes to determine
        the file format.
        
        Args:
            file_path: Path to the data file
            
        Returns:
            DataFormat enum indicating the detected format
            
        Raises:
            DataError: If file does not exist
        """
        path = Path(file_path)
        
        if not path.exists():
            raise DataError(
                message=f"File not found: {file_path}",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
                file_path=str(file_path),
            )
        
        # First try extension-based detection
        ext = path.suffix.lower()
        if ext in self.EXTENSION_MAP:
            return self.EXTENSION_MAP[ext]
        
        # Fall back to magic bytes detection
        return self._detect_by_magic_bytes(path)
    
    def _detect_by_magic_bytes(self, path: Path) -> DataFormat:
        """
        Detect format using magic bytes at the start of the file.
        
        Args:
            path: Path to the file
            
        Returns:
            Detected DataFormat or UNKNOWN
        """
        try:
            with open(path, "rb") as f:
                header = f.read(8)
            
            # Check for Parquet (PAR1 at start or end)
            if header[:4] == b"PAR1":
                return DataFormat.PARQUET
            
            # Check for Excel/ZIP format
            if header[:4] == b"PK\x03\x04":
                return DataFormat.EXCEL
            
            # Check if it looks like CSV (text-based)
            try:
                header.decode("utf-8")
                return DataFormat.CSV
            except UnicodeDecodeError:
                pass
            
            return DataFormat.UNKNOWN
            
        except Exception:
            return DataFormat.UNKNOWN

    def import_file(
        self,
        file_path: str | Path,
        format: DataFormat | None = None,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Import a data file into a Pandas DataFrame.
        
        Args:
            file_path: Path to the data file
            format: Optional format override. If None, format is auto-detected.
            **kwargs: Additional arguments passed to the underlying reader
            
        Returns:
            Pandas DataFrame containing the imported data
            
        Raises:
            DataError: If import fails or format is unsupported
        """
        path = Path(file_path)
        
        if not path.exists():
            raise DataError(
                message=f"File not found: {file_path}",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
                file_path=str(file_path),
            )
        
        # Detect format if not specified
        if format is None:
            format = self.detect_format(path)
        
        if format == DataFormat.UNKNOWN:
            raise DataError(
                message=f"Unable to detect file format: {file_path}",
                error_code=ErrorCodes.DATA_FORMAT_INVALID,
                file_path=str(file_path),
            )
        
        # Import based on format
        try:
            if format == DataFormat.CSV:
                return self._import_csv(path, **kwargs)
            elif format == DataFormat.EXCEL:
                return self._import_excel(path, **kwargs)
            elif format == DataFormat.PARQUET:
                return self._import_parquet(path, **kwargs)
            else:
                raise DataError(
                    message=f"Unsupported format: {format}",
                    error_code=ErrorCodes.DATA_FORMAT_INVALID,
                    file_path=str(file_path),
                )
        except DataError:
            raise
        except Exception as e:
            raise DataError(
                message=f"Failed to import file: {e}",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
                file_path=str(file_path),
                details={"original_error": str(e)},
            )
    
    def _import_csv(self, path: Path, **kwargs: Any) -> pd.DataFrame:
        """Import a CSV file using Pandas."""
        csv_kwargs = {"parse_dates": True}
        csv_kwargs.update(kwargs)
        return pd.read_csv(path, **csv_kwargs)
    
    def _import_excel(self, path: Path, **kwargs: Any) -> pd.DataFrame:
        """Import an Excel file using Pandas."""
        return pd.read_excel(path, **kwargs)
    
    def _import_parquet(self, path: Path, **kwargs: Any) -> pd.DataFrame:
        """Import a Parquet file using Pandas."""
        return pd.read_parquet(path, **kwargs)
    
    def get_file_info(self, file_path: str | Path) -> dict[str, Any]:
        """Get information about a data file without fully loading it."""
        path = Path(file_path)
        
        if not path.exists():
            raise DataError(
                message=f"File not found: {file_path}",
                error_code=ErrorCodes.DATA_IMPORT_FAILED,
                file_path=str(file_path),
            )
        
        format = self.detect_format(path)
        size_bytes = path.stat().st_size
        
        info: dict[str, Any] = {
            "format": format,
            "size_bytes": size_bytes,
            "estimated_rows": None,
            "columns": None,
        }
        
        try:
            if format == DataFormat.CSV:
                df = pd.read_csv(path, nrows=1)
                info["columns"] = list(df.columns)
            elif format == DataFormat.PARQUET:
                df = pd.read_parquet(path)
                info["columns"] = list(df.columns)
                info["estimated_rows"] = len(df)
            elif format == DataFormat.EXCEL:
                df = pd.read_excel(path, nrows=1)
                info["columns"] = list(df.columns)
        except Exception:
            pass
        
        return info


def import_data(file_path: str | Path, **kwargs: Any) -> pd.DataFrame:
    """Convenience function to import a data file."""
    importer = DataImporter()
    return importer.import_file(file_path, **kwargs)


__all__ = ["DataFormat", "DataImporter", "import_data"]
