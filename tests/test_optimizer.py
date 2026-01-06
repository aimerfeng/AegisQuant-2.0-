"""
Property-Based Tests for Parameter Optimizer

This module contains property-based tests using Hypothesis to verify
the correctness properties of the Parameter Optimizer implementation.

Property 16: Optimizer Parameter Bounds
    For any optimization result, all parameter values in the result
    must fall within the user-specified parameter ranges.

Validates: Requirements 9.2
"""
import math
from typing import Any, Dict, List, Tuple

import pytest
from hypothesis import given, settings, strategies as st, assume

from core.optimizer import (
    OptimizationAlgorithm,
    OptimizationConfig,
    OptimizationObjective,
    OptimizationResult,
    OptimizationSummary,
    ParameterOptimizer,
    ParameterRange,
    ParameterType,
    ProcessIsolatedOptimizer,
    int_range,
    float_range,
    categorical,
)


# ==================== Hypothesis Strategies ====================

@st.composite
def int_parameter_range_strategy(draw):
    """Generate a valid integer parameter range."""
    name = draw(st.text(
        min_size=1, 
        max_size=20,
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), min_codepoint=97, max_codepoint=122)
    ))
    # Ensure name is valid identifier
    name = f"param_{name}" if name else "param_default"
    
    low = draw(st.integers(min_value=0, max_value=50))
    high = draw(st.integers(min_value=low + 1, max_value=100))
    step = draw(st.integers(min_value=1, max_value=max(1, (high - low) // 2)))
    
    return ParameterRange(
        name=name,
        param_type=ParameterType.INT,
        low=low,
        high=high,
        step=step,
    )


@st.composite
def float_parameter_range_strategy(draw):
    """Generate a valid float parameter range."""
    name = draw(st.text(
        min_size=1, 
        max_size=20,
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), min_codepoint=97, max_codepoint=122)
    ))
    name = f"param_{name}" if name else "param_default"
    
    low = draw(st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False))
    high = draw(st.floats(min_value=low + 0.1, max_value=100.0, allow_nan=False, allow_infinity=False))
    
    return ParameterRange(
        name=name,
        param_type=ParameterType.FLOAT,
        low=low,
        high=high,
    )


@st.composite
def categorical_parameter_range_strategy(draw):
    """Generate a valid categorical parameter range."""
    name = draw(st.text(
        min_size=1, 
        max_size=20,
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll'), min_codepoint=97, max_codepoint=122)
    ))
    name = f"param_{name}" if name else "param_default"
    
    num_choices = draw(st.integers(min_value=2, max_value=5))
    choices = [f"choice_{i}" for i in range(num_choices)]
    
    return ParameterRange(
        name=name,
        param_type=ParameterType.CATEGORICAL,
        choices=choices,
    )


@st.composite
def parameter_range_strategy(draw):
    """Generate any valid parameter range."""
    param_type = draw(st.sampled_from([
        ParameterType.INT,
        ParameterType.FLOAT,
        ParameterType.CATEGORICAL,
    ]))
    
    if param_type == ParameterType.INT:
        return draw(int_parameter_range_strategy())
    elif param_type == ParameterType.FLOAT:
        return draw(float_parameter_range_strategy())
    else:
        return draw(categorical_parameter_range_strategy())


@st.composite
def optimization_config_strategy(draw):
    """Generate a valid optimization configuration."""
    # Generate 1-3 parameter ranges with unique names
    num_params = draw(st.integers(min_value=1, max_value=3))
    param_ranges = []
    used_names = set()
    
    for i in range(num_params):
        param = draw(parameter_range_strategy())
        # Ensure unique names
        base_name = param.name
        counter = 0
        while param.name in used_names:
            param = ParameterRange(
                name=f"{base_name}_{counter}",
                param_type=param.param_type,
                low=param.low,
                high=param.high,
                step=param.step,
                choices=param.choices,
            )
            counter += 1
        used_names.add(param.name)
        param_ranges.append(param)
    
    return OptimizationConfig(
        parameter_ranges=param_ranges,
        objective=OptimizationObjective.SHARPE_RATIO,
        algorithm=OptimizationAlgorithm.TPE,
        n_trials=5,  # Small number for testing
        n_jobs=1,
        seed=42,
    )


# ==================== Test Classes ====================

class TestOptimizerParameterBounds:
    """
    Property 16: Optimizer Parameter Bounds
    
    *For any* optimization result, all parameter values in the result
    must fall within the user-specified parameter ranges.
    
    **Validates: Requirements 9.2**
    """
    
    def test_int_parameter_bounds(self) -> None:
        """Test that integer parameters stay within bounds."""
        param_range = int_range("period", 5, 50, step=5)
        
        config = OptimizationConfig(
            parameter_ranges=[param_range],
            objective=OptimizationObjective.SHARPE_RATIO,
            n_trials=10,
            n_jobs=1,
            seed=42,
        )
        
        def objective(params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
            # Simple objective: maximize the parameter value
            return float(params["period"]), {"value": float(params["period"])}
        
        optimizer = ParameterOptimizer()
        summary = optimizer.optimize(objective, config)
        
        # Verify all results have parameters within bounds
        for result in summary.all_results:
            if result.status == "complete":
                value = result.params["period"]
                assert param_range.low <= value <= param_range.high, \
                    f"Parameter 'period' value {value} out of bounds [{param_range.low}, {param_range.high}]"
                assert isinstance(value, int), f"Expected int, got {type(value)}"
        
        # Verify best params are within bounds
        if summary.best_params:
            value = summary.best_params["period"]
            assert param_range.low <= value <= param_range.high
    
    def test_float_parameter_bounds(self) -> None:
        """Test that float parameters stay within bounds."""
        param_range = float_range("threshold", 0.1, 1.0)
        
        config = OptimizationConfig(
            parameter_ranges=[param_range],
            objective=OptimizationObjective.SHARPE_RATIO,
            n_trials=10,
            n_jobs=1,
            seed=42,
        )
        
        def objective(params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
            return params["threshold"], {"value": params["threshold"]}
        
        optimizer = ParameterOptimizer()
        summary = optimizer.optimize(objective, config)
        
        for result in summary.all_results:
            if result.status == "complete":
                value = result.params["threshold"]
                assert param_range.low <= value <= param_range.high, \
                    f"Parameter 'threshold' value {value} out of bounds"
    
    def test_categorical_parameter_bounds(self) -> None:
        """Test that categorical parameters stay within choices."""
        param_range = categorical("mode", ["fast", "medium", "slow"])
        
        config = OptimizationConfig(
            parameter_ranges=[param_range],
            objective=OptimizationObjective.SHARPE_RATIO,
            n_trials=10,
            n_jobs=1,
            seed=42,
        )
        
        mode_values = {"fast": 1.0, "medium": 0.5, "slow": 0.2}
        
        def objective(params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
            return mode_values[params["mode"]], {}
        
        optimizer = ParameterOptimizer()
        summary = optimizer.optimize(objective, config)
        
        for result in summary.all_results:
            if result.status == "complete":
                value = result.params["mode"]
                assert value in param_range.choices, \
                    f"Parameter 'mode' value {value} not in choices {param_range.choices}"
    
    def test_multiple_parameters_bounds(self) -> None:
        """Test that multiple parameters all stay within their bounds."""
        param_ranges = [
            int_range("fast_period", 5, 20),
            int_range("slow_period", 20, 100),
            float_range("threshold", 0.0, 1.0),
        ]
        
        config = OptimizationConfig(
            parameter_ranges=param_ranges,
            objective=OptimizationObjective.SHARPE_RATIO,
            n_trials=10,
            n_jobs=1,
            seed=42,
        )
        
        def objective(params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
            # Objective that uses all parameters
            value = params["fast_period"] + params["slow_period"] + params["threshold"]
            return value, {}
        
        optimizer = ParameterOptimizer()
        summary = optimizer.optimize(objective, config)
        
        for result in summary.all_results:
            if result.status == "complete":
                for param_range in param_ranges:
                    value = result.params[param_range.name]
                    assert param_range.validate_value(value), \
                        f"Parameter '{param_range.name}' value {value} out of bounds"
    
    @given(config=optimization_config_strategy())
    @settings(max_examples=20, deadline=30000)
    def test_property_all_results_within_bounds(
        self,
        config: OptimizationConfig,
    ) -> None:
        """
        Property: All optimization results must have parameters within specified bounds.
        
        Feature: titan-quant, Property 16: Optimizer Parameter Bounds
        **Validates: Requirements 9.2**
        """
        def objective(params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
            # Simple objective that sums all numeric parameters
            total = 0.0
            for name, value in params.items():
                if isinstance(value, (int, float)):
                    total += float(value)
                else:
                    # Categorical - use index
                    total += 1.0
            return total, {"sum": total}
        
        optimizer = ParameterOptimizer()
        summary = optimizer.optimize(objective, config)
        
        # Verify all results
        for result in summary.all_results:
            if result.status == "complete":
                is_valid, violations = optimizer.validate_params_in_bounds(
                    result.params, config
                )
                assert is_valid, f"Parameter bounds violated: {violations}"
        
        # Verify best params
        if summary.best_params:
            is_valid, violations = optimizer.validate_params_in_bounds(
                summary.best_params, config
            )
            assert is_valid, f"Best params bounds violated: {violations}"
    
    def test_validate_params_in_bounds_method(self) -> None:
        """Test the validate_params_in_bounds helper method."""
        param_ranges = [
            int_range("period", 10, 50),
            float_range("threshold", 0.0, 1.0),
            categorical("mode", ["a", "b", "c"]),
        ]
        
        config = OptimizationConfig(
            parameter_ranges=param_ranges,
            objective=OptimizationObjective.SHARPE_RATIO,
            n_trials=1,
        )
        
        optimizer = ParameterOptimizer()
        
        # Valid params
        valid_params = {"period": 25, "threshold": 0.5, "mode": "b"}
        is_valid, violations = optimizer.validate_params_in_bounds(valid_params, config)
        assert is_valid
        assert len(violations) == 0
        
        # Invalid int (out of range)
        invalid_params = {"period": 100, "threshold": 0.5, "mode": "b"}
        is_valid, violations = optimizer.validate_params_in_bounds(invalid_params, config)
        assert not is_valid
        assert len(violations) == 1
        assert "period" in violations[0]
        
        # Invalid float (out of range)
        invalid_params = {"period": 25, "threshold": 2.0, "mode": "b"}
        is_valid, violations = optimizer.validate_params_in_bounds(invalid_params, config)
        assert not is_valid
        assert len(violations) == 1
        assert "threshold" in violations[0]
        
        # Invalid categorical (not in choices)
        invalid_params = {"period": 25, "threshold": 0.5, "mode": "invalid"}
        is_valid, violations = optimizer.validate_params_in_bounds(invalid_params, config)
        assert not is_valid
        assert len(violations) == 1
        assert "mode" in violations[0]
        
        # Missing parameter
        missing_params = {"period": 25, "threshold": 0.5}
        is_valid, violations = optimizer.validate_params_in_bounds(missing_params, config)
        assert not is_valid
        assert "Missing parameter" in violations[0]


class TestParameterRangeValidation:
    """Unit tests for ParameterRange validation."""
    
    def test_int_range_validation(self) -> None:
        """Test integer range validation."""
        param = int_range("test", 10, 50)
        
        assert param.validate_value(10)  # Lower bound
        assert param.validate_value(50)  # Upper bound
        assert param.validate_value(30)  # Middle
        assert not param.validate_value(5)  # Below
        assert not param.validate_value(60)  # Above
    
    def test_float_range_validation(self) -> None:
        """Test float range validation."""
        param = float_range("test", 0.0, 1.0)
        
        assert param.validate_value(0.0)
        assert param.validate_value(1.0)
        assert param.validate_value(0.5)
        assert not param.validate_value(-0.1)
        assert not param.validate_value(1.1)
    
    def test_categorical_validation(self) -> None:
        """Test categorical validation."""
        param = categorical("test", ["a", "b", "c"])
        
        assert param.validate_value("a")
        assert param.validate_value("b")
        assert param.validate_value("c")
        assert not param.validate_value("d")
        assert not param.validate_value("")
    
    def test_invalid_range_raises_error(self) -> None:
        """Test that invalid ranges raise errors."""
        # Low >= High
        with pytest.raises(ValueError):
            ParameterRange("test", ParameterType.INT, low=50, high=10)
        
        # Missing bounds for numeric
        with pytest.raises(ValueError):
            ParameterRange("test", ParameterType.INT, low=10)
        
        # Empty choices for categorical
        with pytest.raises(ValueError):
            ParameterRange("test", ParameterType.CATEGORICAL, choices=[])
        
        # Empty name
        with pytest.raises(ValueError):
            ParameterRange("", ParameterType.INT, low=0, high=10)


class TestOptimizationConfig:
    """Unit tests for OptimizationConfig."""
    
    def test_config_creation(self) -> None:
        """Test basic config creation."""
        config = OptimizationConfig(
            parameter_ranges=[int_range("test", 0, 10)],
            objective=OptimizationObjective.SHARPE_RATIO,
            n_trials=100,
        )
        
        assert len(config.parameter_ranges) == 1
        assert config.objective == OptimizationObjective.SHARPE_RATIO
        assert config.n_trials == 100
        assert config.direction == "maximize"
    
    def test_max_drawdown_sets_minimize(self) -> None:
        """Test that MAX_DRAWDOWN objective sets minimize direction."""
        config = OptimizationConfig(
            parameter_ranges=[int_range("test", 0, 10)],
            objective=OptimizationObjective.MAX_DRAWDOWN,
            n_trials=10,
        )
        
        assert config.direction == "minimize"
    
    def test_config_serialization(self) -> None:
        """Test config serialization to dict."""
        config = OptimizationConfig(
            parameter_ranges=[
                int_range("period", 5, 50),
                float_range("threshold", 0.0, 1.0),
            ],
            objective=OptimizationObjective.TOTAL_RETURN,
            algorithm=OptimizationAlgorithm.CMA_ES,
            n_trials=50,
            n_jobs=4,
            seed=123,
        )
        
        config_dict = config.to_dict()
        
        assert len(config_dict["parameter_ranges"]) == 2
        assert config_dict["objective"] == "total_return"
        assert config_dict["algorithm"] == "cma_es"
        assert config_dict["n_trials"] == 50
        assert config_dict["n_jobs"] == 4
        assert config_dict["seed"] == 123


class TestOptimizerBasicFunctionality:
    """Unit tests for basic optimizer functionality."""
    
    def test_simple_optimization(self) -> None:
        """Test a simple optimization run."""
        config = OptimizationConfig(
            parameter_ranges=[int_range("x", 0, 10)],
            objective=OptimizationObjective.SHARPE_RATIO,
            n_trials=10,
            n_jobs=1,
            seed=42,
        )
        
        def objective(params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
            # Maximize x
            return float(params["x"]), {"x": float(params["x"])}
        
        optimizer = ParameterOptimizer()
        summary = optimizer.optimize(objective, config)
        
        assert summary.optimization_id is not None
        assert summary.total_trials == 10
        assert summary.successful_trials > 0
        assert summary.best_value is not None
        assert "x" in summary.best_params
    
    def test_optimization_with_callback(self) -> None:
        """Test optimization with callback function."""
        config = OptimizationConfig(
            parameter_ranges=[int_range("x", 0, 10)],
            n_trials=5,
            n_jobs=1,
            seed=42,
        )
        
        callback_results = []
        
        def callback(result: OptimizationResult) -> None:
            callback_results.append(result)
        
        def objective(params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
            return float(params["x"]), {}
        
        optimizer = ParameterOptimizer()
        optimizer.optimize(objective, config, callback=callback)
        
        assert len(callback_results) == 5
    
    def test_optimization_history(self) -> None:
        """Test getting optimization history."""
        config = OptimizationConfig(
            parameter_ranges=[int_range("x", 0, 10)],
            n_trials=5,
            n_jobs=1,
            seed=42,
        )
        
        def objective(params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
            return float(params["x"]), {}
        
        optimizer = ParameterOptimizer()
        optimizer.optimize(objective, config)
        
        history = optimizer.get_optimization_history()
        assert len(history) == 5
    
    def test_failed_trials_handled(self) -> None:
        """Test that failed trials are handled gracefully."""
        config = OptimizationConfig(
            parameter_ranges=[int_range("x", 0, 10)],
            n_trials=5,
            n_jobs=1,
            seed=42,
        )
        
        call_count = [0]
        
        def objective(params: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
            call_count[0] += 1
            if call_count[0] == 3:
                raise ValueError("Simulated failure")
            return float(params["x"]), {}
        
        optimizer = ParameterOptimizer()
        summary = optimizer.optimize(objective, config)
        
        # Should complete despite failure - pruned trials may not be in results
        # The important thing is that the optimization completes successfully
        assert summary.successful_trials >= 4  # At least 4 successful
        assert summary.best_value is not None  # Found a best value


class TestConvenienceFunctions:
    """Unit tests for convenience functions."""
    
    def test_int_range_function(self) -> None:
        """Test int_range convenience function."""
        param = int_range("period", 5, 50, step=5)
        
        assert param.name == "period"
        assert param.param_type == ParameterType.INT
        assert param.low == 5
        assert param.high == 50
        assert param.step == 5
    
    def test_float_range_function(self) -> None:
        """Test float_range convenience function."""
        param = float_range("threshold", 0.0, 1.0, step=0.1)
        
        assert param.name == "threshold"
        assert param.param_type == ParameterType.FLOAT
        assert param.low == 0.0
        assert param.high == 1.0
        assert param.step == 0.1
    
    def test_float_range_log_scale(self) -> None:
        """Test float_range with log scale."""
        param = float_range("learning_rate", 1e-5, 1e-1, log=True)
        
        assert param.name == "learning_rate"
        assert param.param_type == ParameterType.LOG_FLOAT
        assert param.log is True
    
    def test_categorical_function(self) -> None:
        """Test categorical convenience function."""
        param = categorical("mode", ["fast", "slow"])
        
        assert param.name == "mode"
        assert param.param_type == ParameterType.CATEGORICAL
        assert param.choices == ["fast", "slow"]
