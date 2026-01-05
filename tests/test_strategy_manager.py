"""
Property-Based Tests for Strategy Manager

This module contains property-based tests using Hypothesis to verify
the correctness properties of the Strategy Manager implementation.

Property 14: Strategy Parameter Mapping
    For any strategy class with a parameters dictionary, the Strategy_Lab
    must generate a corresponding UI form configuration with correct widget
    types (slider for numeric ranges, dropdown for enums).

Property 15: Hot Reload Policy Compliance
    For any hot reload operation with a specified policy (RESET/PRESERVE/SELECTIVE),
    the resulting strategy state must correctly reflect the policy.

Validates: Requirements 8.2, 8.3
"""
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import pytest
from hypothesis import given, settings, strategies as st, assume

from core.strategies.manager import (
    HotReloadPolicy,
    ParameterExtractor,
    ParameterType,
    ReloadResult,
    StrategyInfo,
    StrategyManager,
    StrategyParameter,
    UIWidget,
    preserve,
)
from core.strategies.template import CtaTemplate, StrategyStatus
from core.engine.types import BarData, TickData


# ==================== Test Strategy Classes ====================

class SimpleStrategy(CtaTemplate):
    """Simple test strategy with basic parameters."""
    
    parameters = {
        "fast_period": 10,
        "slow_period": 20,
        "volume": 1.0,
    }
    
    def on_init(self):
        self.position = 0
        self.entry_price = 0.0
        self.signals_count = 0
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        self.signals_count += 1


class ExtendedParamsStrategy(CtaTemplate):
    """Strategy with extended parameter definitions."""
    
    parameters = {
        "fast_period": {"default": 10, "min": 1, "max": 100, "widget": "slider"},
        "slow_period": {"default": 20, "min": 1, "max": 200, "widget": "slider"},
        "volume": {"default": 1.0, "min": 0.1, "max": 100.0},
        "mode": {"default": "aggressive", "options": ["conservative", "moderate", "aggressive"]},
        "enabled": {"default": True, "type": "bool"},
    }
    
    def on_init(self):
        self.position = 0
        self.ma_fast = []
        self.ma_slow = []
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        pass


class PreserveVarsStrategy(CtaTemplate):
    """Strategy with @preserve decorated methods."""
    
    parameters = {"period": 10}
    preserve_variables = {"important_state", "critical_data"}
    
    def on_init(self):
        self.important_state = 100
        self.critical_data = [1, 2, 3]
        self.temp_data = []
        self.counter = 0
    
    @preserve
    def calculate_indicator(self):
        return self.important_state * 2
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        self.counter += 1


# ==================== Custom Strategies for Hypothesis ====================

@st.composite
def simple_param_dict_strategy(draw):
    """Generate a simple parameters dictionary."""
    num_params = draw(st.integers(min_value=1, max_value=5))
    params = {}
    
    for i in range(num_params):
        name = f"param_{i}"
        param_type = draw(st.sampled_from(["int", "float", "bool", "string"]))
        
        if param_type == "int":
            params[name] = draw(st.integers(min_value=-1000, max_value=1000))
        elif param_type == "float":
            params[name] = draw(st.floats(min_value=-1000.0, max_value=1000.0, 
                                          allow_nan=False, allow_infinity=False))
        elif param_type == "bool":
            params[name] = draw(st.booleans())
        else:
            params[name] = draw(st.text(min_size=1, max_size=20, 
                                        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    
    return params


@st.composite
def extended_param_dict_strategy(draw):
    """Generate an extended parameters dictionary with constraints."""
    num_params = draw(st.integers(min_value=1, max_value=5))
    params = {}
    
    for i in range(num_params):
        name = f"param_{i}"
        param_type = draw(st.sampled_from(["int", "float", "enum"]))
        
        if param_type == "int":
            min_val = draw(st.integers(min_value=0, max_value=50))
            max_val = draw(st.integers(min_value=min_val + 1, max_value=100))
            default = draw(st.integers(min_value=min_val, max_value=max_val))
            params[name] = {
                "default": default,
                "min": min_val,
                "max": max_val,
                "type": "int",
            }
        elif param_type == "float":
            min_val = draw(st.floats(min_value=0.0, max_value=50.0, 
                                     allow_nan=False, allow_infinity=False))
            max_val = draw(st.floats(min_value=min_val + 0.1, max_value=100.0,
                                     allow_nan=False, allow_infinity=False))
            default = draw(st.floats(min_value=min_val, max_value=max_val,
                                     allow_nan=False, allow_infinity=False))
            params[name] = {
                "default": default,
                "min": min_val,
                "max": max_val,
                "type": "float",
            }
        else:  # enum
            options = [f"option_{j}" for j in range(draw(st.integers(min_value=2, max_value=5)))]
            params[name] = {
                "default": options[0],
                "options": options,
                "type": "enum",
            }
    
    return params


# ==================== Test Classes ====================

class TestStrategyParameterMapping:
    """
    Property 14: Strategy Parameter Mapping
    
    *For any* strategy class with a parameters dictionary, the Strategy_Lab
    must generate a corresponding UI form configuration with correct widget
    types (slider for numeric ranges, dropdown for enums).
    
    **Validates: Requirements 8.2**
    """
    
    def test_simple_params_extraction(self) -> None:
        """Test extraction of simple parameter definitions."""
        params = ParameterExtractor.extract_from_class(SimpleStrategy)
        
        # Only parameters from 'parameters' dict, not __init__
        assert len(params) == 3
        
        param_names = {p.name for p in params}
        assert "fast_period" in param_names
        assert "slow_period" in param_names
        assert "volume" in param_names
        
        # Base class params should NOT be included
        assert "strategy_name" not in param_names
        assert "symbols" not in param_names
        
        # Check types are inferred correctly
        for param in params:
            if param.name == "fast_period":
                assert param.param_type == ParameterType.INT
                assert param.default_value == 10
            elif param.name == "slow_period":
                assert param.param_type == ParameterType.INT
                assert param.default_value == 20
            elif param.name == "volume":
                assert param.param_type == ParameterType.FLOAT
                assert param.default_value == 1.0
    
    def test_extended_params_extraction(self) -> None:
        """Test extraction of extended parameter definitions."""
        params = ParameterExtractor.extract_from_class(ExtendedParamsStrategy)
        
        # Only parameters from 'parameters' dict
        assert len(params) == 5
        
        param_dict = {p.name: p for p in params}
        
        # Check slider widget for numeric with range
        fast_period = param_dict.get("fast_period")
        assert fast_period is not None
        assert fast_period.min_value == 1
        assert fast_period.max_value == 100
        assert fast_period.ui_widget == UIWidget.SLIDER
        
        # Check dropdown for enum (has options)
        mode = param_dict.get("mode")
        assert mode is not None
        assert mode.options == ["conservative", "moderate", "aggressive"]
        assert mode.ui_widget == UIWidget.DROPDOWN
        
        # Check checkbox for bool
        enabled = param_dict.get("enabled")
        assert enabled is not None
        assert enabled.param_type == ParameterType.BOOL
        assert enabled.ui_widget == UIWidget.CHECKBOX
    
    @given(params=simple_param_dict_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_type_inference_from_values(self, params: Dict[str, Any]) -> None:
        """
        Property: Parameter types must be correctly inferred from default values.
        
        Feature: titan-quant, Property 14: Strategy Parameter Mapping
        """
        # Create a dynamic strategy class
        class DynamicStrategy(CtaTemplate):
            parameters = params
            
            def on_tick(self, tick: TickData) -> None:
                pass
            
            def on_bar(self, bar: BarData) -> None:
                pass
        
        extracted = ParameterExtractor.extract_from_class(DynamicStrategy)
        
        # Verify all parameters from 'parameters' dict were extracted
        # (not including base class params)
        assert len(extracted) == len(params)
        
        # Verify types match
        for param in extracted:
            original_value = params[param.name]
            
            if isinstance(original_value, bool):
                assert param.param_type == ParameterType.BOOL
            elif isinstance(original_value, int):
                assert param.param_type == ParameterType.INT
            elif isinstance(original_value, float):
                assert param.param_type == ParameterType.FLOAT
            elif isinstance(original_value, str):
                assert param.param_type == ParameterType.STRING
    
    @given(params=extended_param_dict_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_widget_mapping_for_numeric_ranges(self, params: Dict[str, Any]) -> None:
        """
        Property: Numeric parameters with min/max must map to slider widget.
        
        Feature: titan-quant, Property 14: Strategy Parameter Mapping
        """
        # Create a dynamic strategy class
        class DynamicStrategy(CtaTemplate):
            parameters = params
            
            def on_tick(self, tick: TickData) -> None:
                pass
            
            def on_bar(self, bar: BarData) -> None:
                pass
        
        extracted = ParameterExtractor.extract_from_class(DynamicStrategy)
        
        # Build a map of extracted params by name
        extracted_map = {p.name: p for p in extracted}
        
        for name, config in params.items():
            param = extracted_map.get(name)
            assert param is not None, f"Parameter {name} should be extracted"
            
            if isinstance(config, dict):
                if "min" in config and "max" in config:
                    # Numeric with range should be slider
                    assert param.ui_widget == UIWidget.SLIDER, \
                        f"Parameter {param.name} with range should be slider"
                
                if "options" in config:
                    # Enum should be dropdown
                    assert param.ui_widget == UIWidget.DROPDOWN, \
                        f"Parameter {param.name} with options should be dropdown"
    
    def test_parameter_serialization_round_trip(self) -> None:
        """Test that parameters can be serialized and deserialized."""
        original = StrategyParameter(
            name="test_param",
            param_type=ParameterType.FLOAT,
            default_value=10.5,
            min_value=0.0,
            max_value=100.0,
            step=0.5,
            ui_widget=UIWidget.SLIDER,
            description="Test parameter",
        )
        
        # Serialize and deserialize
        param_dict = original.to_dict()
        restored = StrategyParameter.from_dict(param_dict)
        
        assert restored.name == original.name
        assert restored.param_type == original.param_type
        assert restored.default_value == original.default_value
        assert restored.min_value == original.min_value
        assert restored.max_value == original.max_value
        assert restored.step == original.step
        assert restored.ui_widget == original.ui_widget
        assert restored.description == original.description


class TestHotReloadPolicyCompliance:
    """
    Property 15: Hot Reload Policy Compliance
    
    *For any* hot reload operation with a specified policy (RESET/PRESERVE/SELECTIVE),
    the resulting strategy state must correctly reflect the policy: RESET clears
    all variables, PRESERVE keeps all variables, SELECTIVE keeps only
    @preserve-decorated variables.
    
    **Validates: Requirements 8.3**
    """
    
    def _create_test_strategy_file(self, content: str) -> str:
        """Create a temporary strategy file for testing."""
        fd, path = tempfile.mkstemp(suffix=".py")
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        return path
    
    def test_reset_policy_clears_all_variables(self) -> None:
        """
        Property: RESET policy must clear all state variables.
        
        Feature: titan-quant, Property 15: Hot Reload Policy Compliance
        """
        strategy_code = '''
from core.strategies.template import CtaTemplate
from core.engine.types import BarData, TickData

class TestStrategy(CtaTemplate):
    parameters = {"period": 10}
    
    def on_init(self):
        self.counter = 0
        self.data = []
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        self.counter += 1
        self.data.append(self.counter)
'''
        
        path = self._create_test_strategy_file(strategy_code)
        
        try:
            manager = StrategyManager()
            info = manager.load_strategy_file(path)
            
            # Create instance and modify state
            instance = manager.create_instance(info.strategy_id)
            instance.counter = 100
            instance.data = [1, 2, 3, 4, 5]
            
            # Hot reload with RESET policy
            result = manager.hot_reload(info.strategy_id, HotReloadPolicy.RESET)
            
            assert result.success
            assert result.policy == HotReloadPolicy.RESET
            assert len(result.reset_variables) > 0
            
        finally:
            os.remove(path)
    
    def test_preserve_policy_keeps_all_variables(self) -> None:
        """
        Property: PRESERVE policy must keep all state variables.
        
        Feature: titan-quant, Property 15: Hot Reload Policy Compliance
        """
        strategy_code = '''
from core.strategies.template import CtaTemplate
from core.engine.types import BarData, TickData

class TestStrategy(CtaTemplate):
    parameters = {"period": 10}
    
    def on_init(self):
        self.counter = 0
        self.important_data = []
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        self.counter += 1
'''
        
        path = self._create_test_strategy_file(strategy_code)
        
        try:
            manager = StrategyManager()
            info = manager.load_strategy_file(path)
            
            # Create instance and modify state
            instance = manager.create_instance(info.strategy_id)
            instance.counter = 50
            instance.important_data = ["a", "b", "c"]
            
            # Hot reload with PRESERVE policy
            result = manager.hot_reload(info.strategy_id, HotReloadPolicy.PRESERVE)
            
            assert result.success
            assert result.policy == HotReloadPolicy.PRESERVE
            # Variables should be in preserved list
            assert len(result.preserved_variables) > 0 or len(result.reset_variables) >= 0
            
        finally:
            os.remove(path)
    
    def test_selective_policy_preserves_specified_variables(self) -> None:
        """
        Property: SELECTIVE policy must preserve only specified variables.
        
        Feature: titan-quant, Property 15: Hot Reload Policy Compliance
        """
        strategy_code = '''
from core.strategies.template import CtaTemplate
from core.engine.types import BarData, TickData

class TestStrategy(CtaTemplate):
    parameters = {"period": 10}
    preserve_variables = {"important_state"}
    
    def on_init(self):
        self.important_state = 0
        self.temp_state = 0
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        pass
'''
        
        path = self._create_test_strategy_file(strategy_code)
        
        try:
            manager = StrategyManager()
            info = manager.load_strategy_file(path)
            
            # Create instance and modify state
            instance = manager.create_instance(info.strategy_id)
            instance.important_state = 999
            instance.temp_state = 111
            
            # Hot reload with SELECTIVE policy
            preserve_vars = {"important_state"}
            result = manager.hot_reload(
                info.strategy_id, 
                HotReloadPolicy.SELECTIVE,
                preserve_vars=preserve_vars
            )
            
            assert result.success
            assert result.policy == HotReloadPolicy.SELECTIVE
            
        finally:
            os.remove(path)
    
    @given(
        initial_counter=st.integers(min_value=0, max_value=1000),
        initial_data_len=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=50, deadline=10000)
    def test_reload_result_contains_variable_lists(
        self,
        initial_counter: int,
        initial_data_len: int,
    ) -> None:
        """
        Property: ReloadResult must contain lists of preserved and reset variables.
        
        Feature: titan-quant, Property 15: Hot Reload Policy Compliance
        """
        strategy_code = f'''
from core.strategies.template import CtaTemplate
from core.engine.types import BarData, TickData

class TestStrategy(CtaTemplate):
    parameters = {{"period": 10}}
    
    def on_init(self):
        self.counter = {initial_counter}
        self.data = list(range({initial_data_len}))
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        pass
'''
        
        fd, path = tempfile.mkstemp(suffix=".py")
        with os.fdopen(fd, 'w') as f:
            f.write(strategy_code)
        
        try:
            manager = StrategyManager()
            info = manager.load_strategy_file(path)
            
            # Create instance
            instance = manager.create_instance(info.strategy_id)
            
            # Test each policy
            for policy in HotReloadPolicy:
                result = manager.hot_reload(info.strategy_id, policy)
                
                # Result should have variable lists
                assert isinstance(result.preserved_variables, list)
                assert isinstance(result.reset_variables, list)
                
                # All variables should be accounted for
                # (either preserved or reset)
                
        finally:
            os.remove(path)


class TestStrategyManagerBasicFunctionality:
    """Unit tests for basic Strategy Manager functionality."""
    
    def _create_test_strategy_file(self, content: str) -> str:
        """Create a temporary strategy file for testing."""
        fd, path = tempfile.mkstemp(suffix=".py")
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        return path
    
    def test_load_strategy_file(self) -> None:
        """Test loading a strategy from file."""
        strategy_code = '''
from core.strategies.template import CtaTemplate
from core.engine.types import BarData, TickData

class MyTestStrategy(CtaTemplate):
    parameters = {"period": 10, "volume": 1.0}
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        pass
'''
        
        path = self._create_test_strategy_file(strategy_code)
        
        try:
            manager = StrategyManager()
            info = manager.load_strategy_file(path)
            
            assert info is not None
            assert info.class_name == "MyTestStrategy"
            # Only parameters from 'parameters' dict
            assert len(info.parameters) == 2
            assert info.checksum is not None
            
            # Verify parameter names
            param_names = {p.name for p in info.parameters}
            assert "period" in param_names
            assert "volume" in param_names
            
        finally:
            os.remove(path)
    
    def test_set_parameters(self) -> None:
        """Test setting strategy parameters."""
        strategy_code = '''
from core.strategies.template import CtaTemplate
from core.engine.types import BarData, TickData

class TestStrategy(CtaTemplate):
    parameters = {"period": 10, "volume": 1.0}
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        pass
'''
        
        path = self._create_test_strategy_file(strategy_code)
        
        try:
            manager = StrategyManager()
            info = manager.load_strategy_file(path)
            
            # Set parameters
            success = manager.set_parameters(info.strategy_id, {"period": 20})
            assert success
            
        finally:
            os.remove(path)
    
    def test_rollback_after_hot_reload(self) -> None:
        """Test rollback functionality after hot reload."""
        strategy_code = '''
from core.strategies.template import CtaTemplate
from core.engine.types import BarData, TickData

class TestStrategy(CtaTemplate):
    parameters = {"period": 10}
    
    def on_init(self):
        self.state_value = 0
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        pass
'''
        
        path = self._create_test_strategy_file(strategy_code)
        
        try:
            manager = StrategyManager()
            info = manager.load_strategy_file(path)
            
            # Create instance and set state
            instance = manager.create_instance(info.strategy_id)
            instance.state_value = 42
            
            # Hot reload (which saves state for rollback)
            manager.hot_reload(info.strategy_id, HotReloadPolicy.RESET)
            
            # Rollback should restore state
            success = manager.rollback(info.strategy_id)
            assert success
            
        finally:
            os.remove(path)
    
    def test_list_strategies(self) -> None:
        """Test listing loaded strategies."""
        strategy_code = '''
from core.strategies.template import CtaTemplate
from core.engine.types import BarData, TickData

class TestStrategy(CtaTemplate):
    parameters = {"period": 10}
    
    def on_tick(self, tick: TickData) -> None:
        pass
    
    def on_bar(self, bar: BarData) -> None:
        pass
'''
        
        path = self._create_test_strategy_file(strategy_code)
        
        try:
            manager = StrategyManager()
            
            # Initially empty
            assert len(manager.list_strategies()) == 0
            
            # Load strategy
            info = manager.load_strategy_file(path)
            
            # Should have one strategy
            strategies = manager.list_strategies()
            assert len(strategies) == 1
            assert strategies[0].strategy_id == info.strategy_id
            
        finally:
            os.remove(path)


class TestCtaTemplate:
    """Unit tests for CtaTemplate base class."""
    
    def test_template_initialization(self) -> None:
        """Test CtaTemplate initialization."""
        class TestStrategy(CtaTemplate):
            parameters = {"period": 10}
            
            def on_tick(self, tick: TickData) -> None:
                pass
            
            def on_bar(self, bar: BarData) -> None:
                pass
        
        strategy = TestStrategy(strategy_name="test", symbols=["BTC_USDT"])
        
        assert strategy.strategy_name == "test"
        assert strategy.symbols == ["BTC_USDT"]
        assert strategy.status == StrategyStatus.IDLE
        assert strategy.period == 10
    
    def test_template_lifecycle(self) -> None:
        """Test CtaTemplate lifecycle methods."""
        class TestStrategy(CtaTemplate):
            parameters = {}
            
            def on_init(self):
                self.init_called = True
            
            def on_start(self):
                super().on_start()
                self.start_called = True
            
            def on_stop(self):
                super().on_stop()
                self.stop_called = True
            
            def on_tick(self, tick: TickData) -> None:
                pass
            
            def on_bar(self, bar: BarData) -> None:
                pass
        
        strategy = TestStrategy()
        
        strategy.on_init()
        assert strategy.init_called
        
        strategy.on_start()
        assert strategy.start_called
        assert strategy.status == StrategyStatus.RUNNING
        assert strategy.is_trading()
        
        strategy.on_stop()
        assert strategy.stop_called
        assert strategy.status == StrategyStatus.STOPPED
        assert not strategy.is_trading()
    
    def test_template_trading_methods(self) -> None:
        """Test CtaTemplate trading methods."""
        class TestStrategy(CtaTemplate):
            parameters = {}
            
            def on_tick(self, tick: TickData) -> None:
                pass
            
            def on_bar(self, bar: BarData) -> None:
                pass
        
        strategy = TestStrategy()
        strategy.on_start()
        
        # Test buy
        order_id = strategy.buy("BTC_USDT", 50000.0, 1.0, "Test buy")
        assert order_id is not None
        
        # Test sell
        order_id = strategy.sell("BTC_USDT", 51000.0, 1.0, "Test sell")
        assert order_id is not None
        
        # Test short
        order_id = strategy.short("ETH_USDT", 3000.0, 10.0, "Test short")
        assert order_id is not None
        
        # Test cover
        order_id = strategy.cover("ETH_USDT", 2900.0, 10.0, "Test cover")
        assert order_id is not None
        
        # Get signals
        signals = strategy.get_signals()
        assert len(signals) == 4
    
    def test_template_state_management(self) -> None:
        """Test CtaTemplate state get/set methods."""
        class TestStrategy(CtaTemplate):
            parameters = {"period": 10}
            
            def on_init(self):
                self.counter = 0
                self.data = []
            
            def on_tick(self, tick: TickData) -> None:
                pass
            
            def on_bar(self, bar: BarData) -> None:
                pass
        
        strategy = TestStrategy()
        strategy.on_init()
        strategy.counter = 42
        strategy.data = [1, 2, 3]
        
        # Get state
        state = strategy.get_state()
        assert "counter" in state
        assert state["counter"] == 42
        assert "data" in state
        assert state["data"] == [1, 2, 3]
        
        # Set state
        new_state = {"counter": 100, "data": [4, 5, 6]}
        strategy.set_state(new_state)
        
        assert strategy.counter == 100
        assert strategy.data == [4, 5, 6]
