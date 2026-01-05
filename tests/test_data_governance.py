"""
Property-Based Tests for Data Governance Module

This module contains property-based tests using Hypothesis to verify
the correctness properties of the Data Governance Hub implementation.

Properties tested:
- Property 3: Data Format Detection
- Property 4: Missing Value Fill Correctness
- Property 5: Outlier Detection Accuracy
- Property 6: Timestamp Alignment Validation
- Property 7: Data Persistence Round-Trip

Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st, assume

from core.data.importer import DataFormat, DataImporter
from core.data.cleaner import (
    FillMethod,
    DataQualityReport,
    CleaningConfig,
    DataCleaner,
)
from core.data.storage import (
    ParquetStorage,
    StorageConfig,
    BAR_REQUIRED_COLUMNS,
    TICK_REQUIRED_COLUMNS,
)


# ============================================================================
# Custom Strategies for Test Data Generation
# ============================================================================

@st.composite
def valid_numeric_dataframe(draw, min_rows: int = 5, max_rows: int = 100) -> pd.DataFrame:
    """Generate a valid numeric DataFrame for testing."""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    
    base_time = datetime(2024, 1, 1, 9, 0, 0)
    timestamps = [base_time + timedelta(minutes=i) for i in range(n_rows)]
    
    base_price = draw(st.floats(min_value=100.0, max_value=10000.0))
    
    opens = [base_price + draw(st.floats(min_value=-10.0, max_value=10.0)) for _ in range(n_rows)]
    highs = [o + abs(draw(st.floats(min_value=0.0, max_value=5.0))) for o in opens]
    lows = [o - abs(draw(st.floats(min_value=0.0, max_value=5.0))) for o in opens]
    closes = [draw(st.floats(min_value=l, max_value=h)) for l, h in zip(lows, highs)]
    volumes = [draw(st.floats(min_value=100.0, max_value=10000.0)) for _ in range(n_rows)]
    
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


@st.composite
def dataframe_with_missing_values(draw, min_rows: int = 10, max_rows: int = 50) -> tuple[pd.DataFrame, dict[str, list[int]]]:
    """Generate a DataFrame with some missing values and track which indices are null."""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    
    base_time = datetime(2024, 1, 1, 9, 0, 0)
    timestamps = [base_time + timedelta(minutes=i) for i in range(n_rows)]
    
    values = [draw(st.floats(min_value=100.0, max_value=1000.0)) for _ in range(n_rows)]
    
    missing_indices: dict[str, list[int]] = {"value": []}
    n_missing = draw(st.integers(min_value=1, max_value=max(1, n_rows // 4)))
    
    possible_indices = list(range(1, n_rows))
    if possible_indices:
        null_indices = draw(st.lists(
            st.sampled_from(possible_indices),
            min_size=min(n_missing, len(possible_indices)),
            max_size=min(n_missing, len(possible_indices)),
            unique=True,
        ))
        
        for idx in null_indices:
            values[idx] = np.nan
            missing_indices["value"].append(idx)
    
    df = pd.DataFrame({
        "timestamp": timestamps,
        "value": values,
    })
    
    return df, missing_indices


@st.composite
def dataframe_with_outliers(draw, min_rows: int = 20, max_rows: int = 100) -> tuple[pd.DataFrame, list[int]]:
    """Generate a DataFrame with known outliers."""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    
    mean = 500.0
    std = 50.0
    
    values = []
    outlier_indices = []
    
    for i in range(n_rows):
        is_outlier = draw(st.booleans()) and draw(st.integers(min_value=1, max_value=20)) == 1
        
        if is_outlier:
            direction = draw(st.sampled_from([-1, 1]))
            outlier_value = mean + direction * (3.5 + draw(st.floats(min_value=0.1, max_value=2.0))) * std
            values.append(outlier_value)
            outlier_indices.append(i)
        else:
            normal_value = mean + draw(st.floats(min_value=-2.0, max_value=2.0)) * std
            values.append(normal_value)
    
    base_time = datetime(2024, 1, 1, 9, 0, 0)
    timestamps = [base_time + timedelta(minutes=i) for i in range(n_rows)]
    
    df = pd.DataFrame({
        "timestamp": timestamps,
        "value": values,
    })
    
    return df, outlier_indices


@st.composite
def bar_dataframe(draw, min_rows: int = 5, max_rows: int = 50) -> pd.DataFrame:
    """Generate a valid bar DataFrame for storage testing."""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    
    base_time = datetime(2024, 1, 1, 9, 0, 0)
    timestamps = [base_time + timedelta(minutes=i) for i in range(n_rows)]
    
    opens = [draw(st.floats(min_value=100.0, max_value=1000.0)) for _ in range(n_rows)]
    highs = [o + abs(draw(st.floats(min_value=0.0, max_value=10.0))) for o in opens]
    lows = [o - abs(draw(st.floats(min_value=0.0, max_value=10.0))) for o in opens]
    closes = [draw(st.floats(min_value=l, max_value=h)) for l, h in zip(lows, highs)]
    volumes = [draw(st.floats(min_value=100.0, max_value=10000.0)) for _ in range(n_rows)]
    
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


@st.composite
def tick_dataframe(draw, min_rows: int = 5, max_rows: int = 50) -> pd.DataFrame:
    """Generate a valid tick DataFrame for storage testing."""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    
    base_time = datetime(2024, 1, 1, 9, 0, 0)
    timestamps = [base_time + timedelta(seconds=i) for i in range(n_rows)]
    
    base_price = draw(st.floats(min_value=100.0, max_value=10000.0))
    
    return pd.DataFrame({
        "timestamp": timestamps,
        "last_price": [base_price + draw(st.floats(min_value=-5.0, max_value=5.0)) for _ in range(n_rows)],
        "volume": [draw(st.floats(min_value=0.1, max_value=100.0)) for _ in range(n_rows)],
        "bid_price_1": [base_price - 0.1 for _ in range(n_rows)],
        "bid_volume_1": [draw(st.floats(min_value=1.0, max_value=100.0)) for _ in range(n_rows)],
        "ask_price_1": [base_price + 0.1 for _ in range(n_rows)],
        "ask_volume_1": [draw(st.floats(min_value=1.0, max_value=100.0)) for _ in range(n_rows)],
    })


# ============================================================================
# Property 3: Data Format Detection
# ============================================================================

class TestDataFormatDetection:
    """
    Property 3: Data Format Detection
    
    *For any* valid data file in supported formats (CSV, Excel, Parquet),
    the Data_Governance_Hub must correctly identify the format and
    successfully parse the data without data loss.
    
    **Validates: Requirements 2.1**
    """
    
    @given(df=valid_numeric_dataframe())
    @settings(max_examples=100, deadline=10000)
    def test_csv_format_detection_and_parsing(self, df: pd.DataFrame) -> None:
        """
        Property: For any valid DataFrame saved as CSV, the importer must
        detect CSV format and parse without data loss.
        
        Feature: titan-quant, Property 3: Data Format Detection
        """
        importer = DataImporter()
        
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_path = f.name
        
        try:
            df.to_csv(temp_path, index=False)
            
            detected_format = importer.detect_format(temp_path)
            assert detected_format == DataFormat.CSV, \
                f"Expected CSV format, got {detected_format}"
            
            imported_df = importer.import_file(temp_path)
            
            assert len(imported_df) == len(df), \
                f"Row count mismatch: expected {len(df)}, got {len(imported_df)}"
            
            assert len(imported_df.columns) == len(df.columns), \
                f"Column count mismatch: expected {len(df.columns)}, got {len(imported_df.columns)}"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @given(df=valid_numeric_dataframe())
    @settings(max_examples=100, deadline=10000)
    def test_parquet_format_detection_and_parsing(self, df: pd.DataFrame) -> None:
        """
        Property: For any valid DataFrame saved as Parquet, the importer must
        detect Parquet format and parse without data loss.
        
        Feature: titan-quant, Property 3: Data Format Detection
        """
        importer = DataImporter()
        
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            temp_path = f.name
        
        try:
            df.to_parquet(temp_path, index=False)
            
            detected_format = importer.detect_format(temp_path)
            assert detected_format == DataFormat.PARQUET, \
                f"Expected PARQUET format, got {detected_format}"
            
            imported_df = importer.import_file(temp_path)
            
            assert len(imported_df) == len(df), \
                f"Row count mismatch: expected {len(df)}, got {len(imported_df)}"
            
            assert list(imported_df.columns) == list(df.columns), \
                f"Column mismatch: expected {list(df.columns)}, got {list(imported_df.columns)}"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


# ============================================================================
# Property 4: Missing Value Fill Correctness
# ============================================================================

class TestMissingValueFillCorrectness:
    """
    Property 4: Missing Value Fill Correctness
    
    *For any* dataset with missing values, after applying Forward Fill or
    Linear interpolation, the resulting dataset must have no missing values,
    and filled values must conform to the selected fill strategy.
    
    **Validates: Requirements 2.2**
    """
    
    @given(data=dataframe_with_missing_values())
    @settings(max_examples=100, deadline=10000)
    def test_forward_fill_removes_all_nulls(
        self, data: tuple[pd.DataFrame, dict[str, list[int]]]
    ) -> None:
        """
        Property: For any DataFrame with missing values, forward fill must
        result in zero null values.
        
        Feature: titan-quant, Property 4: Missing Value Fill Correctness
        """
        df, missing_indices = data
        
        assume(df["value"].isna().sum() > 0)
        
        cleaner = DataCleaner()
        config = CleaningConfig(fill_method=FillMethod.FORWARD_FILL)
        
        cleaned_df = cleaner.clean_data(df, config)
        
        for col in cleaned_df.columns:
            null_count = cleaned_df[col].isna().sum()
            assert null_count == 0, \
                f"Column {col} still has {null_count} null values after forward fill"
    
    @given(data=dataframe_with_missing_values())
    @settings(max_examples=100, deadline=10000)
    def test_linear_interpolation_removes_all_nulls(
        self, data: tuple[pd.DataFrame, dict[str, list[int]]]
    ) -> None:
        """
        Property: For any DataFrame with missing values, linear interpolation
        must result in zero null values.
        
        Feature: titan-quant, Property 4: Missing Value Fill Correctness
        """
        df, missing_indices = data
        
        assume(df["value"].isna().sum() > 0)
        
        cleaner = DataCleaner()
        config = CleaningConfig(fill_method=FillMethod.LINEAR)
        
        cleaned_df = cleaner.clean_data(df, config)
        
        for col in cleaned_df.columns:
            null_count = cleaned_df[col].isna().sum()
            assert null_count == 0, \
                f"Column {col} still has {null_count} null values after linear interpolation"
    
    @given(data=dataframe_with_missing_values())
    @settings(max_examples=100, deadline=10000)
    def test_forward_fill_uses_previous_value(
        self, data: tuple[pd.DataFrame, dict[str, list[int]]]
    ) -> None:
        """
        Property: For any forward-filled value, it must equal the most recent
        non-null value before it.
        
        Feature: titan-quant, Property 4: Missing Value Fill Correctness
        """
        df, missing_indices = data
        
        assume(len(missing_indices.get("value", [])) > 0)
        
        cleaner = DataCleaner()
        config = CleaningConfig(fill_method=FillMethod.FORWARD_FILL)
        
        cleaned_df = cleaner.clean_data(df, config)
        
        original_values = df["value"].tolist()
        filled_values = cleaned_df["value"].tolist()
        
        for idx in missing_indices.get("value", []):
            prev_idx = idx - 1
            while prev_idx >= 0 and pd.isna(original_values[prev_idx]):
                prev_idx -= 1
            
            if prev_idx >= 0:
                expected = original_values[prev_idx]
                actual = filled_values[idx]
                assert actual == expected, \
                    f"Forward fill at index {idx}: expected {expected}, got {actual}"


# ============================================================================
# Property 5: Outlier Detection Accuracy
# ============================================================================

class TestOutlierDetectionAccuracy:
    """
    Property 5: Outlier Detection Accuracy
    
    *For any* dataset, all values marked as outliers must have an absolute
    z-score greater than 3.0 (or the configured threshold), and no unmarked
    values should exceed this threshold.
    
    **Validates: Requirements 2.3**
    """
    
    @given(data=dataframe_with_outliers())
    @settings(max_examples=100, deadline=10000)
    def test_detected_outliers_exceed_threshold(
        self, data: tuple[pd.DataFrame, list[int]]
    ) -> None:
        """
        Property: For any value marked as an outlier, its |z-score| must be > threshold.
        
        Feature: titan-quant, Property 5: Outlier Detection Accuracy
        """
        df, known_outliers = data
        threshold = 3.0
        
        cleaner = DataCleaner()
        config = CleaningConfig(outlier_threshold=threshold)
        
        report = cleaner.analyze_quality(df, config)
        detected_outliers = report.outliers.get("value", [])
        
        z_scores = cleaner.get_z_scores(df, "value")
        
        for idx in detected_outliers:
            z = abs(z_scores.iloc[idx])
            assert z > threshold, \
                f"Detected outlier at index {idx} has |z-score| = {z} <= {threshold}"
    
    @given(data=dataframe_with_outliers())
    @settings(max_examples=100, deadline=10000)
    def test_non_outliers_within_threshold(
        self, data: tuple[pd.DataFrame, list[int]]
    ) -> None:
        """
        Property: For any value NOT marked as an outlier, its |z-score| must be <= threshold.
        
        Feature: titan-quant, Property 5: Outlier Detection Accuracy
        """
        df, _ = data
        threshold = 3.0
        
        cleaner = DataCleaner()
        config = CleaningConfig(outlier_threshold=threshold)
        
        report = cleaner.analyze_quality(df, config)
        detected_outliers = set(report.outliers.get("value", []))
        
        z_scores = cleaner.get_z_scores(df, "value")
        
        for idx in range(len(df)):
            if idx not in detected_outliers:
                z = abs(z_scores.iloc[idx])
                assert z <= threshold, \
                    f"Non-outlier at index {idx} has |z-score| = {z} > {threshold}"
    
    @given(
        threshold=st.floats(min_value=1.5, max_value=5.0),
        data=dataframe_with_outliers(min_rows=30, max_rows=100),
    )
    @settings(max_examples=100, deadline=10000)
    def test_outlier_detection_respects_custom_threshold(
        self, threshold: float, data: tuple[pd.DataFrame, list[int]]
    ) -> None:
        """
        Property: Outlier detection must respect the configured threshold value.
        
        Feature: titan-quant, Property 5: Outlier Detection Accuracy
        """
        df, _ = data
        
        cleaner = DataCleaner()
        config = CleaningConfig(outlier_threshold=threshold)
        
        report = cleaner.analyze_quality(df, config)
        detected_outliers = report.outliers.get("value", [])
        
        z_scores = cleaner.get_z_scores(df, "value")
        
        for idx in detected_outliers:
            z = abs(z_scores.iloc[idx])
            assert z > threshold, \
                f"Outlier at {idx} has |z| = {z} <= threshold {threshold}"


# ============================================================================
# Property 6: Timestamp Alignment Validation
# ============================================================================

class TestTimestampAlignmentValidation:
    """
    Property 6: Timestamp Alignment Validation
    
    *For any* set of multi-contract data, the alignment validation function
    must correctly identify all timestamp misalignments where corresponding
    data points do not exist across all contracts.
    
    **Validates: Requirements 2.4**
    """
    
    @given(
        n_rows=st.integers(min_value=10, max_value=50),
        missing_count=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100, deadline=10000)
    def test_detects_missing_timestamps(self, n_rows: int, missing_count: int) -> None:
        """
        Property: For any set of DataFrames with different timestamps,
        validation must detect all misalignments.
        
        Feature: titan-quant, Property 6: Timestamp Alignment Validation
        """
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        all_timestamps = [base_time + timedelta(minutes=i) for i in range(n_rows)]
        
        df1 = pd.DataFrame({
            "timestamp": all_timestamps,
            "value": [100.0 + i for i in range(n_rows)],
        })
        
        missing_indices = list(range(1, min(missing_count + 1, n_rows)))
        df2_timestamps = [ts for i, ts in enumerate(all_timestamps) if i not in missing_indices]
        df2 = pd.DataFrame({
            "timestamp": df2_timestamps,
            "value": [200.0 + i for i in range(len(df2_timestamps))],
        })
        
        cleaner = DataCleaner()
        issues = cleaner.validate_alignment([df1, df2], "timestamp")
        
        assert len(issues) > 0, "Expected alignment issues to be detected"
        
        has_df1_issue = any("DataFrame 1" in issue for issue in issues)
        assert has_df1_issue, \
            f"Expected DataFrame 1 to be flagged for missing timestamps. Issues: {issues}"
    
    @given(n_rows=st.integers(min_value=5, max_value=30))
    @settings(max_examples=100, deadline=10000)
    def test_no_issues_for_aligned_data(self, n_rows: int) -> None:
        """
        Property: For DataFrames with identical timestamps, validation
        must report no alignment issues.
        
        Feature: titan-quant, Property 6: Timestamp Alignment Validation
        """
        base_time = datetime(2024, 1, 1, 9, 0, 0)
        timestamps = [base_time + timedelta(minutes=i) for i in range(n_rows)]
        
        df1 = pd.DataFrame({
            "timestamp": timestamps,
            "value": [100.0 + i for i in range(n_rows)],
        })
        
        df2 = pd.DataFrame({
            "timestamp": timestamps,
            "value": [200.0 + i for i in range(n_rows)],
        })
        
        cleaner = DataCleaner()
        issues = cleaner.validate_alignment([df1, df2], "timestamp")
        
        assert len(issues) == 0, \
            f"Expected no alignment issues for identical timestamps, got: {issues}"


# ============================================================================
# Property 7: Data Persistence Round-Trip
# ============================================================================

class TestDataPersistenceRoundTrip:
    """
    Property 7: Data Persistence Round-Trip
    
    *For any* valid DataFrame, saving to Parquet format and reading back must
    produce an equivalent DataFrame with identical schema and values.
    
    **Validates: Requirements 2.6**
    """
    
    @given(df=bar_dataframe())
    @settings(max_examples=100, deadline=10000)
    def test_bar_data_round_trip(self, df: pd.DataFrame) -> None:
        """
        Property: For any valid bar DataFrame, save and load must produce
        identical data.
        
        Feature: titan-quant, Property 7: Data Persistence Round-Trip
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config = StorageConfig(base_path=temp_dir)
            storage = ParquetStorage(config)
            
            exchange = "test_exchange"
            symbol = "test_symbol"
            interval = "1m"
            
            storage.save_bar_data(df, exchange, symbol, interval)
            loaded_df = storage.load_bar_data(exchange, symbol, interval)
            
            assert len(loaded_df) == len(df), \
                f"Row count mismatch: expected {len(df)}, got {len(loaded_df)}"
            
            assert list(loaded_df.columns) == list(df.columns), \
                f"Column mismatch: expected {list(df.columns)}, got {list(loaded_df.columns)}"
            
            for col in ["open", "high", "low", "close", "volume"]:
                original = df[col].tolist()
                loaded = loaded_df[col].tolist()
                for i, (o, l) in enumerate(zip(original, loaded)):
                    assert abs(o - l) < 1e-10, \
                        f"Value mismatch in {col} at index {i}: {o} vs {l}"
    
    @given(df=tick_dataframe())
    @settings(max_examples=100, deadline=10000)
    def test_tick_data_round_trip(self, df: pd.DataFrame) -> None:
        """
        Property: For any valid tick DataFrame, save and load must produce
        identical data.
        
        Feature: titan-quant, Property 7: Data Persistence Round-Trip
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config = StorageConfig(base_path=temp_dir)
            storage = ParquetStorage(config)
            
            exchange = "test_exchange"
            symbol = "test_symbol"
            date = "2024-01-01"
            
            storage.save_tick_data(df, exchange, symbol, date)
            loaded_df = storage.load_tick_data(exchange, symbol, date)
            
            assert len(loaded_df) == len(df), \
                f"Row count mismatch: expected {len(df)}, got {len(loaded_df)}"
            
            assert list(loaded_df.columns) == list(df.columns), \
                f"Column mismatch: expected {list(df.columns)}, got {list(loaded_df.columns)}"
    
    @given(
        exchange=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10),
        symbol=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=3, max_size=15),
        df=bar_dataframe(),
    )
    @settings(max_examples=100, deadline=10000)
    def test_storage_path_organization(
        self, exchange: str, symbol: str, df: pd.DataFrame
    ) -> None:
        """
        Property: Data must be stored in the correct directory structure
        organized by exchange/symbol.
        
        Feature: titan-quant, Property 7: Data Persistence Round-Trip
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config = StorageConfig(base_path=temp_dir)
            storage = ParquetStorage(config)
            
            interval = "1m"
            file_path = storage.save_bar_data(df, exchange, symbol, interval)
            
            expected_path_parts = [
                temp_dir, "bars", exchange.lower(), symbol.lower(), f"{interval}.parquet"
            ]
            expected_path = os.path.join(*expected_path_parts)
            
            assert os.path.normpath(file_path) == os.path.normpath(expected_path), \
                f"Path mismatch: expected {expected_path}, got {file_path}"
            
            assert os.path.exists(file_path), f"File not created at {file_path}"


# ============================================================================
# Unit Tests for Basic Functionality
# ============================================================================

class TestDataImporterUnit:
    """Unit tests for DataImporter basic functionality."""
    
    def test_detect_csv_format(self) -> None:
        """Test CSV format detection by extension."""
        importer = DataImporter()
        
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_path = f.name
        
        try:
            pd.DataFrame({"a": [1, 2, 3]}).to_csv(temp_path, index=False)
            assert importer.detect_format(temp_path) == DataFormat.CSV
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_detect_parquet_format(self) -> None:
        """Test Parquet format detection by extension."""
        importer = DataImporter()
        
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            temp_path = f.name
        
        try:
            pd.DataFrame({"a": [1, 2, 3]}).to_parquet(temp_path, index=False)
            assert importer.detect_format(temp_path) == DataFormat.PARQUET
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_import_csv_file(self) -> None:
        """Test importing a CSV file."""
        importer = DataImporter()
        
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_path = f.name
        
        try:
            original_df = pd.DataFrame({
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="min"),
                "value": [1.0, 2.0, 3.0, 4.0, 5.0],
            })
            original_df.to_csv(temp_path, index=False)
            
            imported_df = importer.import_file(temp_path)
            
            assert len(imported_df) == 5
            assert "timestamp" in imported_df.columns
            assert "value" in imported_df.columns
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestDataCleanerUnit:
    """Unit tests for DataCleaner basic functionality."""
    
    def test_forward_fill_basic(self) -> None:
        """Test basic forward fill functionality."""
        cleaner = DataCleaner()
        config = CleaningConfig(fill_method=FillMethod.FORWARD_FILL)
        
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="min"),
            "value": [1.0, np.nan, np.nan, 4.0, 5.0],
        })
        
        cleaned = cleaner.clean_data(df, config)
        
        assert cleaned["value"].isna().sum() == 0
        assert cleaned["value"].iloc[1] == 1.0
        assert cleaned["value"].iloc[2] == 1.0
    
    def test_linear_interpolation_basic(self) -> None:
        """Test basic linear interpolation functionality."""
        cleaner = DataCleaner()
        config = CleaningConfig(fill_method=FillMethod.LINEAR)
        
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="min"),
            "value": [1.0, np.nan, np.nan, 4.0, 5.0],
        })
        
        cleaned = cleaner.clean_data(df, config)
        
        assert cleaned["value"].isna().sum() == 0
        assert abs(cleaned["value"].iloc[1] - 2.0) < 0.01
        assert abs(cleaned["value"].iloc[2] - 3.0) < 0.01
    
    def test_outlier_detection_basic(self) -> None:
        """Test basic outlier detection."""
        cleaner = DataCleaner()
        config = CleaningConfig(outlier_threshold=3.0)
        
        values = [100.0] * 50 + [500.0]
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=51, freq="min"),
            "value": values,
        })
        
        report = cleaner.analyze_quality(df, config)
        
        assert "value" in report.outliers
        assert 50 in report.outliers["value"]
    
    def test_alignment_validation_basic(self) -> None:
        """Test basic timestamp alignment validation."""
        cleaner = DataCleaner()
        
        timestamps = pd.date_range("2024-01-01", periods=5, freq="min")
        df1 = pd.DataFrame({"timestamp": timestamps, "value": [1, 2, 3, 4, 5]})
        df2 = pd.DataFrame({"timestamp": timestamps[:3], "value": [1, 2, 3]})
        
        issues = cleaner.validate_alignment([df1, df2], "timestamp")
        
        assert len(issues) > 0


class TestParquetStorageUnit:
    """Unit tests for ParquetStorage basic functionality."""
    
    def test_save_and_load_bar_data(self) -> None:
        """Test saving and loading bar data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = StorageConfig(base_path=temp_dir)
            storage = ParquetStorage(config)
            
            df = pd.DataFrame({
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="min"),
                "open": [100.0, 101.0, 102.0, 103.0, 104.0],
                "high": [101.0, 102.0, 103.0, 104.0, 105.0],
                "low": [99.0, 100.0, 101.0, 102.0, 103.0],
                "close": [100.5, 101.5, 102.5, 103.5, 104.5],
                "volume": [1000.0, 1100.0, 1200.0, 1300.0, 1400.0],
            })
            
            storage.save_bar_data(df, "binance", "btc_usdt", "1m")
            loaded = storage.load_bar_data("binance", "btc_usdt", "1m")
            
            assert len(loaded) == 5
            assert list(loaded.columns) == list(df.columns)
    
    def test_save_and_load_tick_data(self) -> None:
        """Test saving and loading tick data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = StorageConfig(base_path=temp_dir)
            storage = ParquetStorage(config)
            
            df = pd.DataFrame({
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="s"),
                "last_price": [100.0, 100.1, 100.2, 100.3, 100.4],
                "volume": [10.0, 11.0, 12.0, 13.0, 14.0],
            })
            
            storage.save_tick_data(df, "binance", "btc_usdt", "2024-01-01")
            loaded = storage.load_tick_data("binance", "btc_usdt", "2024-01-01")
            
            assert len(loaded) == 5
    
    def test_list_exchanges(self) -> None:
        """Test listing available exchanges."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = StorageConfig(base_path=temp_dir)
            storage = ParquetStorage(config)
            
            df = pd.DataFrame({
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="min"),
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "volume": [1000.0] * 5,
            })
            
            storage.save_bar_data(df, "binance", "btc_usdt", "1m")
            storage.save_bar_data(df, "okx", "eth_usdt", "1m")
            
            from core.data.storage import DataType
            exchanges = storage.list_exchanges(DataType.BAR)
            
            assert "binance" in exchanges
            assert "okx" in exchanges
    
    def test_missing_columns_raises_error(self) -> None:
        """Test that missing required columns raises an error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = StorageConfig(base_path=temp_dir)
            storage = ParquetStorage(config)
            
            df = pd.DataFrame({
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="min"),
                "open": [100.0] * 5,
            })
            
            from core.exceptions import DataError
            with pytest.raises(DataError):
                storage.save_bar_data(df, "binance", "btc_usdt", "1m")
