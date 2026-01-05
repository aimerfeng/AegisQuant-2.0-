"""
Data Cleaner Module

This module provides data cleaning functionality for the Titan-Quant system.
It includes missing value detection and filling, outlier detection using
the 3σ rule, and timestamp alignment validation.

Requirements:
- 2.2: Missing value detection and filling (Forward Fill, Linear)
- 2.3: Outlier detection (3σ rule)
- 2.4: Timestamp alignment validation for multi-contract data
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from core.exceptions import DataError, ErrorCodes


class FillMethod(Enum):
    """Methods for filling missing values."""
    FORWARD_FILL = "ffill"
    LINEAR = "linear"
    DROP = "drop"


@dataclass
class DataQualityReport:
    """Report on data quality issues found during analysis."""
    total_rows: int
    missing_values: dict[str, int] = field(default_factory=dict)
    outliers: dict[str, list[int]] = field(default_factory=dict)
    timestamp_gaps: list[datetime] = field(default_factory=list)
    alignment_issues: list[str] = field(default_factory=list)
    
    @property
    def has_issues(self) -> bool:
        """Check if any quality issues were found."""
        return (
            any(v > 0 for v in self.missing_values.values()) or
            any(len(v) > 0 for v in self.outliers.values()) or
            len(self.timestamp_gaps) > 0 or
            len(self.alignment_issues) > 0
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "total_rows": self.total_rows,
            "missing_values": self.missing_values,
            "outliers": {k: v for k, v in self.outliers.items()},
            "timestamp_gaps": [ts.isoformat() if isinstance(ts, datetime) else str(ts) for ts in self.timestamp_gaps],
            "alignment_issues": self.alignment_issues,
        }


@dataclass
class CleaningConfig:
    """Configuration for data cleaning operations."""
    fill_method: FillMethod = FillMethod.FORWARD_FILL
    outlier_threshold: float = 3.0
    remove_outliers: bool = False
    align_timestamps: bool = True
    timestamp_column: str = "timestamp"
    numeric_columns: list[str] | None = None


class DataCleaner:
    """
    Data cleaning utility for financial time series data.
    
    Provides functionality for:
    - Missing value detection and filling
    - Outlier detection using the 3σ rule
    - Timestamp alignment validation
    """
    
    def __init__(self) -> None:
        """Initialize the DataCleaner."""
        pass
    
    def analyze_quality(
        self,
        df: pd.DataFrame,
        config: CleaningConfig | None = None,
    ) -> DataQualityReport:
        """Analyze data quality and generate a report."""
        if config is None:
            config = CleaningConfig()
        
        report = DataQualityReport(total_rows=len(df))
        
        # Detect missing values
        report.missing_values = self._detect_missing_values(df)
        
        # Detect outliers in numeric columns
        numeric_cols = config.numeric_columns or self._get_numeric_columns(df)
        report.outliers = self._detect_outliers(df, numeric_cols, config.outlier_threshold)
        
        # Detect timestamp gaps if timestamp column exists
        if config.timestamp_column in df.columns:
            report.timestamp_gaps = self._detect_timestamp_gaps(df, config.timestamp_column)
        
        return report
    
    def _detect_missing_values(self, df: pd.DataFrame) -> dict[str, int]:
        """Detect missing values in each column."""
        missing = {}
        for col in df.columns:
            null_count = df[col].isna().sum()
            if null_count > 0:
                missing[col] = int(null_count)
        return missing
    
    def _get_numeric_columns(self, df: pd.DataFrame) -> list[str]:
        """Get list of numeric columns in the DataFrame."""
        return df.select_dtypes(include=[np.number]).columns.tolist()
    
    def _detect_outliers(
        self,
        df: pd.DataFrame,
        columns: list[str],
        threshold: float,
    ) -> dict[str, list[int]]:
        """Detect outliers using the 3σ (z-score) rule."""
        outliers: dict[str, list[int]] = {}
        
        for col in columns:
            if col not in df.columns:
                continue
            
            series = df[col].astype(float)
            mean = series.mean()
            std = series.std()
            
            if std is None or std == 0 or pd.isna(mean):
                continue
            
            z_scores = ((series - mean) / std).abs()
            outlier_mask = z_scores > threshold
            outlier_indices = df.index[outlier_mask].tolist()
            
            if outlier_indices:
                outliers[col] = [int(i) for i in outlier_indices]
        
        return outliers

    def _detect_timestamp_gaps(
        self,
        df: pd.DataFrame,
        timestamp_column: str,
    ) -> list[datetime]:
        """Detect gaps in timestamp sequence."""
        if timestamp_column not in df.columns or len(df) < 2:
            return []
        
        sorted_df = df.sort_values(timestamp_column)
        timestamps = pd.to_datetime(sorted_df[timestamp_column])
        diffs = timestamps.diff()
        median_diff = diffs.dropna().median()
        
        if pd.isna(median_diff):
            return []
        
        gaps = []
        for i, diff in enumerate(diffs):
            if pd.notna(diff) and diff > median_diff * 2:
                ts = timestamps.iloc[i]
                if pd.notna(ts):
                    gaps.append(ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts)
        
        return gaps
    
    def clean_data(
        self,
        df: pd.DataFrame,
        config: CleaningConfig | None = None,
    ) -> pd.DataFrame:
        """Clean the data according to the specified configuration."""
        if config is None:
            config = CleaningConfig()
        
        result = df.copy()
        result = self._fill_missing_values(result, config.fill_method)
        
        if config.remove_outliers:
            numeric_cols = config.numeric_columns or self._get_numeric_columns(result)
            result = self._remove_outliers(result, numeric_cols, config.outlier_threshold)
        
        return result
    
    def _fill_missing_values(
        self,
        df: pd.DataFrame,
        method: FillMethod,
    ) -> pd.DataFrame:
        """Fill missing values using the specified method."""
        if method == FillMethod.DROP:
            return df.dropna()
        
        if method == FillMethod.FORWARD_FILL:
            return df.ffill()
        
        if method == FillMethod.LINEAR:
            result = df.copy()
            numeric_cols = self._get_numeric_columns(df)
            for col in df.columns:
                if df[col].isna().any():
                    if col in numeric_cols:
                        result[col] = result[col].interpolate(method='linear')
                    else:
                        result[col] = result[col].ffill()
            return result
        
        return df
    
    def _remove_outliers(
        self,
        df: pd.DataFrame,
        columns: list[str],
        threshold: float,
    ) -> pd.DataFrame:
        """Remove rows containing outliers."""
        result = df.copy()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            series = result[col].astype(float)
            mean = series.mean()
            std = series.std()
            
            if std is None or std == 0 or pd.isna(mean):
                continue
            
            z_scores = ((series - mean) / std).abs()
            result = result[z_scores <= threshold]
        
        return result

    def validate_alignment(
        self,
        dataframes: list[pd.DataFrame],
        timestamp_column: str = "timestamp",
    ) -> list[str]:
        """Validate timestamp alignment across multiple DataFrames."""
        if len(dataframes) < 2:
            return []
        
        issues = []
        timestamp_sets = []
        
        for i, df in enumerate(dataframes):
            if timestamp_column not in df.columns:
                issues.append(f"DataFrame {i}: Missing timestamp column '{timestamp_column}'")
                continue
            timestamps = set(df[timestamp_column].tolist())
            timestamp_sets.append((i, timestamps))
        
        if len(timestamp_sets) < 2:
            return issues
        
        all_timestamps = set()
        for _, ts_set in timestamp_sets:
            all_timestamps.update(ts_set)
        
        for i, ts_set in timestamp_sets:
            missing = all_timestamps - ts_set
            if missing:
                sample = sorted(list(missing))[:5]
                issues.append(
                    f"DataFrame {i}: Missing {len(missing)} timestamps. Sample: {sample}"
                )
        
        return issues
    
    def get_z_scores(self, df: pd.DataFrame, column: str) -> pd.Series:
        """Calculate z-scores for a column."""
        if column not in df.columns:
            raise DataError(
                message=f"Column not found: {column}",
                error_code=ErrorCodes.DATA_QUALITY_ERROR,
            )
        
        series = df[column].astype(float)
        mean = series.mean()
        std = series.std()
        
        if std is None or std == 0 or pd.isna(mean):
            return pd.Series([0.0] * len(series), index=series.index)
        
        return (series - mean) / std
    
    def mark_outliers(
        self,
        df: pd.DataFrame,
        columns: list[str] | None = None,
        threshold: float = 3.0,
        outlier_column: str = "_is_outlier",
    ) -> pd.DataFrame:
        """Add a column marking rows that contain outliers."""
        if columns is None:
            columns = self._get_numeric_columns(df)
        
        result = df.copy()
        outlier_mask = pd.Series([False] * len(df), index=df.index)
        
        for col in columns:
            if col not in df.columns:
                continue
            
            series = df[col].astype(float)
            mean = series.mean()
            std = series.std()
            
            if std is None or std == 0 or pd.isna(mean):
                continue
            
            z_scores = ((series - mean) / std).abs()
            col_outliers = z_scores > threshold
            outlier_mask = outlier_mask | col_outliers.fillna(False)
        
        result[outlier_column] = outlier_mask
        return result


__all__ = ["FillMethod", "DataQualityReport", "CleaningConfig", "DataCleaner"]
