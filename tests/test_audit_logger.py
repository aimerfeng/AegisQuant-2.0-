"""
Property-Based Tests for Audit Logger

This module contains property-based tests using Hypothesis to verify
the correctness properties of the AuditLogger implementation.

Properties tested:
    - Property 22: Audit Record Completeness
    - Property 23: Audit Chain Hash Integrity
    - Property 24: Audit Integrity Verification

Validates: Requirements 14.2, 14.3, 14.6, 14.8
"""
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck

from utils.audit import (
    ActionType,
    GENESIS_HASH,
    AuditRecord,
    AuditLogger,
    compute_record_hash,
    verify_record_hash,
    compute_file_checksum,
    verify_audit_logs_on_startup,
)
from core.exceptions import AuditIntegrityError


# Custom strategies for generating test data
@st.composite
def audit_record_strategy(draw):
    """Generate valid audit records for testing."""
    user_id = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        whitelist_characters='_-'
    )))
    ip_address = draw(st.from_regex(
        r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',
        fullmatch=True
    ))
    action_type = draw(st.sampled_from([a.value for a in ActionType]))
    
    # Generate action detail as a simple dict
    detail_keys = draw(st.lists(
        st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            whitelist_characters='_'
        )),
        min_size=1,
        max_size=5,
        unique=True
    ))
    detail_values = draw(st.lists(
        st.one_of(
            st.text(min_size=0, max_size=100),
            st.integers(min_value=-1000000, max_value=1000000),
            st.floats(min_value=-1000000, max_value=1000000, allow_nan=False, allow_infinity=False),
            st.booleans()
        ),
        min_size=len(detail_keys),
        max_size=len(detail_keys)
    ))
    action_detail = dict(zip(detail_keys, detail_values))
    
    return {
        "user_id": user_id,
        "ip_address": ip_address,
        "action_type": action_type,
        "action_detail": action_detail,
    }


@st.composite
def param_change_strategy(draw):
    """Generate parameter change data for testing."""
    strategy_id = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        whitelist_characters='_-'
    )))
    param_name = draw(st.text(min_size=1, max_size=30, alphabet=st.characters(
        whitelist_categories=('L', 'N'),
        whitelist_characters='_'
    )))
    old_value = draw(st.one_of(
        st.integers(min_value=-10000, max_value=10000),
        st.floats(min_value=-10000, max_value=10000, allow_nan=False, allow_infinity=False),
        st.text(min_size=0, max_size=50)
    ))
    new_value = draw(st.one_of(
        st.integers(min_value=-10000, max_value=10000),
        st.floats(min_value=-10000, max_value=10000, allow_nan=False, allow_infinity=False),
        st.text(min_size=0, max_size=50)
    ))
    
    return {
        "strategy_id": strategy_id,
        "param_name": param_name,
        "old_value": old_value,
        "new_value": new_value,
    }


@st.composite
def trade_data_strategy(draw):
    """Generate trade data for testing."""
    return {
        "trade_id": draw(st.uuids().map(str)),
        "order_id": draw(st.uuids().map(str)),
        "symbol": draw(st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            whitelist_characters='_'
        ))),
        "exchange": draw(st.sampled_from(["binance", "okx", "huobi", "bybit"])),
        "direction": draw(st.sampled_from(["LONG", "SHORT"])),
        "offset": draw(st.sampled_from(["OPEN", "CLOSE"])),
        "price": draw(st.floats(min_value=0.01, max_value=100000, allow_nan=False, allow_infinity=False)),
        "volume": draw(st.floats(min_value=0.001, max_value=10000, allow_nan=False, allow_infinity=False)),
        "commission": draw(st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False)),
    }


class TestAuditRecordCompleteness:
    """
    Property 22: Audit Record Completeness
    
    *For any* auditable operation (manual trade, parameter change), the audit
    record must contain: user_id, ip_address, timestamp, action_type, and for
    parameter changes, both previous_value and new_value.
    
    **Validates: Requirements 14.2, 14.3**
    """
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        """Create a temporary directory for each test."""
        self.log_dir = tmp_path / "logs"
        self.log_dir.mkdir()
        yield
    
    @given(trade_data=trade_data_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_manual_trade_record_completeness(self, trade_data: dict[str, Any]) -> None:
        """
        Property: For any manual trade, the audit record must contain
        user_id, ip_address, timestamp, and action_type.
        
        Feature: titan-quant, Property 22: Audit Record Completeness
        """
        logger = AuditLogger(log_dir=str(self.log_dir))
        
        user_id = "test_user"
        ip_address = "192.168.1.100"
        
        record_id = logger.log_trade(
            user_id=user_id,
            ip=ip_address,
            trade_data=trade_data,
            is_manual=True
        )
        
        # Retrieve the record
        records = logger.get_records("trading")
        assert len(records) >= 1
        
        record = records[-1]
        
        # Verify completeness
        assert record.record_id == record_id
        assert record.user_id == user_id
        assert record.ip_address == ip_address
        assert record.timestamp is not None
        assert isinstance(record.timestamp, datetime)
        assert record.action_type == ActionType.MANUAL_TRADE.value
        assert record.action_detail == trade_data
    
    @given(param_data=param_change_strategy())
    @settings(max_examples=100, deadline=5000)
    def test_param_change_record_completeness(self, param_data: dict[str, Any]) -> None:
        """
        Property: For any parameter change, the audit record must contain
        user_id, ip_address, timestamp, action_type, previous_value, and new_value.
        
        Feature: titan-quant, Property 22: Audit Record Completeness
        """
        logger = AuditLogger(log_dir=str(self.log_dir))
        
        user_id = "test_user"
        ip_address = "192.168.1.100"
        
        record_id = logger.log_param_change(
            user_id=user_id,
            ip=ip_address,
            strategy_id=param_data["strategy_id"],
            param_name=param_data["param_name"],
            old_value=param_data["old_value"],
            new_value=param_data["new_value"]
        )
        
        # Retrieve the record
        records = logger.get_records("user_action")
        assert len(records) >= 1
        
        record = records[-1]
        
        # Verify completeness
        assert record.record_id == record_id
        assert record.user_id == user_id
        assert record.ip_address == ip_address
        assert record.timestamp is not None
        assert isinstance(record.timestamp, datetime)
        assert record.action_type == ActionType.PARAM_CHANGE.value
        assert record.previous_value == param_data["old_value"]
        assert record.new_value == param_data["new_value"]
        assert record.action_detail["strategy_id"] == param_data["strategy_id"]
        assert record.action_detail["param_name"] == param_data["param_name"]


class TestAuditChainHashIntegrity:
    """
    Property 23: Audit Chain Hash Integrity
    
    *For any* sequence of audit records, each record's hash must be computed
    from the record content combined with the previous record's hash,
    forming an unbroken chain.
    
    **Validates: Requirements 14.6**
    """
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        """Create a temporary directory for each test."""
        self.log_dir = tmp_path / "logs"
        self.log_dir.mkdir()
        yield
    
    @given(num_records=st.integers(min_value=2, max_value=20))
    @settings(max_examples=100, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_chain_hash_links_correctly(self, num_records: int) -> None:
        """
        Property: For any sequence of records, each record's previous_hash
        must equal the record_hash of the preceding record.
        
        Feature: titan-quant, Property 23: Audit Chain Hash Integrity
        """
        # Use a unique directory for each hypothesis example
        import uuid
        unique_dir = Path(tempfile.mkdtemp()) / f"logs_{uuid.uuid4().hex}"
        unique_dir.mkdir(parents=True, exist_ok=True)
        
        logger = AuditLogger(log_dir=str(unique_dir))
        
        # Create multiple records
        for i in range(num_records):
            logger.log_action(
                user_id=f"user_{i}",
                ip="192.168.1.1",
                action_type=ActionType.SYSTEM_START.value,
                detail={"index": i}
            )
        
        # Retrieve records and verify chain
        records = logger.get_records("user_action")
        assert len(records) == num_records
        
        # First record should have genesis hash as previous
        assert records[0].previous_hash == GENESIS_HASH
        
        # Each subsequent record's previous_hash should match prior record's hash
        for i in range(1, len(records)):
            assert records[i].previous_hash == records[i - 1].record_hash, (
                f"Chain broken at record {i}: "
                f"previous_hash={records[i].previous_hash}, "
                f"expected={records[i - 1].record_hash}"
            )
    
    @given(num_records=st.integers(min_value=1, max_value=10))
    @settings(max_examples=100, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_record_hash_is_deterministic(self, num_records: int) -> None:
        """
        Property: For any record, recomputing its hash from its content
        must produce the same hash value.
        
        Feature: titan-quant, Property 23: Audit Chain Hash Integrity
        """
        # Use a unique directory for each hypothesis example
        import uuid
        unique_dir = Path(tempfile.mkdtemp()) / f"logs_{uuid.uuid4().hex}"
        unique_dir.mkdir(parents=True, exist_ok=True)
        
        logger = AuditLogger(log_dir=str(unique_dir))
        
        # Create records
        for i in range(num_records):
            logger.log_action(
                user_id=f"user_{i}",
                ip="192.168.1.1",
                action_type=ActionType.CONFIG_CHANGE.value,
                detail={"setting": f"value_{i}"}
            )
        
        # Retrieve and verify each record's hash
        records = logger.get_records("user_action")
        
        for record in records:
            recomputed_hash = compute_record_hash(record)
            assert record.record_hash == recomputed_hash, (
                f"Hash mismatch for record {record.record_id}: "
                f"stored={record.record_hash}, recomputed={recomputed_hash}"
            )
    
    def test_hash_includes_previous_hash(self) -> None:
        """
        Property: Changing the previous_hash must change the record_hash.
        
        Feature: titan-quant, Property 23: Audit Chain Hash Integrity
        """
        # Create two identical records except for previous_hash
        record1 = AuditRecord(
            record_id="test-1",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            user_id="user1",
            ip_address="192.168.1.1",
            action_type=ActionType.SYSTEM_START.value,
            action_detail={"test": "data"},
            previous_hash=GENESIS_HASH,
        )
        
        record2 = AuditRecord(
            record_id="test-1",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            user_id="user1",
            ip_address="192.168.1.1",
            action_type=ActionType.SYSTEM_START.value,
            action_detail={"test": "data"},
            previous_hash="different_hash_value_here",
        )
        
        # Hashes should be different
        assert record1.record_hash != record2.record_hash


class TestAuditIntegrityVerification:
    """
    Property 24: Audit Integrity Verification
    
    *For any* audit log file, if any record has been modified or deleted,
    the integrity verification must detect the tampering and return false.
    
    **Validates: Requirements 14.8**
    """
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        """Create a temporary directory for each test."""
        self.log_dir = tmp_path / "logs"
        self.log_dir.mkdir()
        yield
    
    @given(num_records=st.integers(min_value=3, max_value=15))
    @settings(max_examples=100, deadline=10000)
    def test_unmodified_logs_pass_verification(self, num_records: int) -> None:
        """
        Property: For any unmodified audit log, integrity verification
        must return True.
        
        Feature: titan-quant, Property 24: Audit Integrity Verification
        """
        logger = AuditLogger(log_dir=str(self.log_dir))
        
        # Create records
        for i in range(num_records):
            logger.log_action(
                user_id=f"user_{i}",
                ip="192.168.1.1",
                action_type=ActionType.USER_LOGIN.value,
                detail={"session": f"session_{i}"}
            )
        
        # Verification should pass
        assert logger.verify_integrity() is True
    
    def test_modified_record_detected(self) -> None:
        """
        Property: If a record's content is modified, integrity verification
        must detect the tampering.
        
        Feature: titan-quant, Property 24: Audit Integrity Verification
        """
        logger = AuditLogger(log_dir=str(self.log_dir))
        
        # Create some records
        for i in range(5):
            logger.log_action(
                user_id=f"user_{i}",
                ip="192.168.1.1",
                action_type=ActionType.USER_LOGIN.value,
                detail={"session": f"session_{i}"}
            )
        
        # Tamper with the log file
        log_file = self.log_dir / "user_action.log"
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Modify a record in the middle
        if len(lines) >= 3:
            record_dict = json.loads(lines[2])
            record_dict["user_id"] = "TAMPERED_USER"
            lines[2] = json.dumps(record_dict) + "\n"
            
            with open(log_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
            
            # Verification should fail
            with pytest.raises(AuditIntegrityError):
                logger.verify_integrity()
    
    def test_deleted_record_detected(self) -> None:
        """
        Property: If a record is deleted, integrity verification
        must detect the tampering.
        
        Feature: titan-quant, Property 24: Audit Integrity Verification
        """
        logger = AuditLogger(log_dir=str(self.log_dir))
        
        # Create some records
        for i in range(5):
            logger.log_action(
                user_id=f"user_{i}",
                ip="192.168.1.1",
                action_type=ActionType.USER_LOGIN.value,
                detail={"session": f"session_{i}"}
            )
        
        # Delete a record from the middle
        log_file = self.log_dir / "user_action.log"
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if len(lines) >= 3:
            # Remove the middle record
            del lines[2]
            
            with open(log_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
            
            # Verification should fail (chain broken)
            with pytest.raises(AuditIntegrityError):
                logger.verify_integrity()
    
    def test_checksum_mismatch_detected(self) -> None:
        """
        Property: If the file checksum doesn't match, integrity verification
        must detect the tampering.
        
        Feature: titan-quant, Property 24: Audit Integrity Verification
        """
        logger = AuditLogger(log_dir=str(self.log_dir))
        
        # Create some records
        for i in range(3):
            logger.log_action(
                user_id=f"user_{i}",
                ip="192.168.1.1",
                action_type=ActionType.USER_LOGIN.value,
                detail={"session": f"session_{i}"}
            )
        
        # Modify the checksum file
        checksum_file = self.log_dir / "user_action.log.checksum"
        with open(checksum_file, "w", encoding="utf-8") as f:
            f.write("invalid_checksum_value")
        
        # Verification should fail
        with pytest.raises(AuditIntegrityError):
            logger.verify_integrity()
    
    def test_startup_verification(self) -> None:
        """
        Property: The startup verification function must correctly
        verify log integrity.
        
        Feature: titan-quant, Property 24: Audit Integrity Verification
        """
        logger = AuditLogger(log_dir=str(self.log_dir))
        
        # Create some records
        for i in range(3):
            logger.log_action(
                user_id=f"user_{i}",
                ip="192.168.1.1",
                action_type=ActionType.SYSTEM_START.value,
                detail={"boot": i}
            )
        
        # Startup verification should pass
        assert verify_audit_logs_on_startup(str(self.log_dir)) is True


class TestAuditRecordSerialization:
    """Unit tests for AuditRecord serialization."""
    
    def test_record_to_json_and_back(self) -> None:
        """Test that records can be serialized and deserialized."""
        record = AuditRecord(
            record_id="test-123",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user_id="user1",
            ip_address="192.168.1.1",
            action_type=ActionType.MANUAL_TRADE.value,
            action_detail={"symbol": "BTC_USDT", "price": 50000.0},
            previous_value=None,
            new_value=None,
            previous_hash=GENESIS_HASH,
        )
        
        json_str = record.to_json()
        restored = AuditRecord.from_json(json_str)
        
        assert restored.record_id == record.record_id
        assert restored.timestamp == record.timestamp
        assert restored.user_id == record.user_id
        assert restored.ip_address == record.ip_address
        assert restored.action_type == record.action_type
        assert restored.action_detail == record.action_detail
        assert restored.previous_hash == record.previous_hash
        assert restored.record_hash == record.record_hash
    
    def test_verify_record_hash_function(self) -> None:
        """Test the verify_record_hash utility function."""
        record = AuditRecord(
            record_id="test-456",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            user_id="user1",
            ip_address="192.168.1.1",
            action_type=ActionType.PARAM_CHANGE.value,
            action_detail={"param": "fast_period"},
            previous_value=10,
            new_value=20,
            previous_hash=GENESIS_HASH,
        )
        
        # Valid record should pass
        assert verify_record_hash(record) is True
        
        # Tampered record should fail
        record.user_id = "tampered_user"
        assert verify_record_hash(record) is False
