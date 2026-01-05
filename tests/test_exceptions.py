"""
Tests for Titan-Quant exception classes.
"""
import pytest

from core.exceptions import (
    TitanQuantError,
    EngineError,
    DataError,
    StrategyError,
    SnapshotError,
    AuditIntegrityError,
    RiskControlError,
    ErrorCodes,
)


class TestTitanQuantError:
    """Tests for the base TitanQuantError class."""
    
    def test_basic_creation(self):
        """Test basic exception creation with message only."""
        error = TitanQuantError("Test error message")
        assert error.message == "Test error message"
        assert error.error_code is None
        assert error.details == {}
        assert str(error) == "Test error message"
    
    def test_with_error_code(self):
        """Test exception with error code."""
        error = TitanQuantError("Test error", error_code="E1001")
        assert error.error_code == "E1001"
        assert str(error) == "[E1001] Test error"
    
    def test_with_details(self):
        """Test exception with additional details."""
        details = {"key": "value", "count": 42}
        error = TitanQuantError("Test error", details=details)
        assert error.details == details
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        error = TitanQuantError(
            "Test error",
            error_code="E1001",
            details={"key": "value"}
        )
        result = error.to_dict()
        assert result["error_type"] == "TitanQuantError"
        assert result["message"] == "Test error"
        assert result["error_code"] == "E1001"
        assert result["details"] == {"key": "value"}
    
    def test_repr(self):
        """Test string representation."""
        error = TitanQuantError("Test", error_code="E1001")
        repr_str = repr(error)
        assert "TitanQuantError" in repr_str
        assert "Test" in repr_str
        assert "E1001" in repr_str


class TestEngineError:
    """Tests for EngineError class."""
    
    def test_basic_creation(self):
        """Test basic engine error creation."""
        error = EngineError("Engine failed")
        assert isinstance(error, TitanQuantError)
        assert error.message == "Engine failed"
    
    def test_with_engine_name(self):
        """Test engine error with engine name."""
        error = EngineError(
            "Initialization failed",
            engine_name="veighna"
        )
        assert error.engine_name == "veighna"
        assert error.details["engine_name"] == "veighna"


class TestDataError:
    """Tests for DataError class."""
    
    def test_basic_creation(self):
        """Test basic data error creation."""
        error = DataError("Invalid data format")
        assert isinstance(error, TitanQuantError)
        assert error.message == "Invalid data format"
    
    def test_with_source_and_path(self):
        """Test data error with source and file path."""
        error = DataError(
            "Import failed",
            data_source="mysql",
            file_path="/data/test.csv"
        )
        assert error.data_source == "mysql"
        assert error.file_path == "/data/test.csv"
        assert error.details["data_source"] == "mysql"
        assert error.details["file_path"] == "/data/test.csv"


class TestStrategyError:
    """Tests for StrategyError class."""
    
    def test_basic_creation(self):
        """Test basic strategy error creation."""
        error = StrategyError("Strategy load failed")
        assert isinstance(error, TitanQuantError)
    
    def test_with_strategy_info(self):
        """Test strategy error with strategy info."""
        error = StrategyError(
            "Hot reload failed",
            strategy_id="strat_001",
            strategy_name="MyStrategy"
        )
        assert error.strategy_id == "strat_001"
        assert error.strategy_name == "MyStrategy"


class TestSnapshotError:
    """Tests for SnapshotError class."""
    
    def test_basic_creation(self):
        """Test basic snapshot error creation."""
        error = SnapshotError("Snapshot not found")
        assert isinstance(error, TitanQuantError)
    
    def test_with_version_info(self):
        """Test snapshot error with version info."""
        error = SnapshotError(
            "Version mismatch",
            snapshot_id="snap_001",
            snapshot_version="1.0.0"
        )
        assert error.snapshot_id == "snap_001"
        assert error.snapshot_version == "1.0.0"


class TestAuditIntegrityError:
    """Tests for AuditIntegrityError class."""
    
    def test_basic_creation(self):
        """Test basic audit integrity error creation."""
        error = AuditIntegrityError("Integrity violation detected")
        assert isinstance(error, TitanQuantError)
    
    def test_with_hash_info(self):
        """Test audit error with hash information."""
        error = AuditIntegrityError(
            "Hash mismatch",
            log_file="trading_audit.log",
            record_id="rec_001",
            expected_hash="abc123",
            actual_hash="def456"
        )
        assert error.log_file == "trading_audit.log"
        assert error.record_id == "rec_001"
        assert error.expected_hash == "abc123"
        assert error.actual_hash == "def456"


class TestRiskControlError:
    """Tests for RiskControlError class."""
    
    def test_basic_creation(self):
        """Test basic risk control error creation."""
        error = RiskControlError("Risk limit exceeded")
        assert isinstance(error, TitanQuantError)
    
    def test_with_risk_info(self):
        """Test risk error with risk information."""
        error = RiskControlError(
            "Daily drawdown exceeded",
            trigger_type="daily_drawdown",
            threshold=0.05,
            actual_value=0.07,
            auto_liquidate=True
        )
        assert error.trigger_type == "daily_drawdown"
        assert error.threshold == 0.05
        assert error.actual_value == 0.07
        assert error.auto_liquidate is True
        assert error.details["auto_liquidate"] is True


class TestErrorCodes:
    """Tests for ErrorCodes constants."""
    
    def test_engine_error_codes(self):
        """Test engine error codes exist."""
        assert ErrorCodes.ENGINE_INIT_FAILED == "E1001"
        assert ErrorCodes.ENGINE_NOT_RUNNING == "E1002"
    
    def test_data_error_codes(self):
        """Test data error codes exist."""
        assert ErrorCodes.DATA_FORMAT_INVALID == "E2001"
        assert ErrorCodes.DATA_IMPORT_FAILED == "E2002"
    
    def test_strategy_error_codes(self):
        """Test strategy error codes exist."""
        assert ErrorCodes.STRATEGY_LOAD_FAILED == "E3001"
        assert ErrorCodes.HOT_RELOAD_FAILED == "E3004"
    
    def test_snapshot_error_codes(self):
        """Test snapshot error codes exist."""
        assert ErrorCodes.SNAPSHOT_NOT_FOUND == "E4001"
        assert ErrorCodes.SNAPSHOT_VERSION_MISMATCH == "E4003"
    
    def test_audit_error_codes(self):
        """Test audit error codes exist."""
        assert ErrorCodes.AUDIT_INTEGRITY_VIOLATION == "E5001"
        assert ErrorCodes.AUDIT_HASH_MISMATCH == "E5002"
    
    def test_risk_error_codes(self):
        """Test risk control error codes exist."""
        assert ErrorCodes.RISK_DRAWDOWN_EXCEEDED == "E6001"
        assert ErrorCodes.RISK_CIRCUIT_BREAKER == "E6004"


class TestExceptionInheritance:
    """Tests for exception inheritance hierarchy."""
    
    def test_all_inherit_from_base(self):
        """Test all exceptions inherit from TitanQuantError."""
        exceptions = [
            EngineError("test"),
            DataError("test"),
            StrategyError("test"),
            SnapshotError("test"),
            AuditIntegrityError("test"),
            RiskControlError("test"),
        ]
        for exc in exceptions:
            assert isinstance(exc, TitanQuantError)
            assert isinstance(exc, Exception)
    
    def test_can_catch_by_base_class(self):
        """Test exceptions can be caught by base class."""
        with pytest.raises(TitanQuantError):
            raise EngineError("Test engine error")
        
        with pytest.raises(TitanQuantError):
            raise RiskControlError("Test risk error")
