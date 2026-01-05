"""
Titan-Quant Strategy Manager

This module implements the strategy management functionality including
parameter parsing, hot reload, and strategy lifecycle management.

Requirements:
    - 8.2: WHEN 策略类定义 parameters 字典, THEN THE Strategy_Lab SHALL 
           自动映射为 UI 表单（数字滑块、下拉选择）
    - 8.3: WHEN 用户修改策略代码并点击"Reload", THEN THE Strategy_Lab SHALL 
           根据 Hot_Reload_Policy 执行热重载
    - 8.4: WHEN 热重载执行, THEN THE Strategy_Lab SHALL 在日志中明确记录
           重载模式和受影响的变量列表
    - 8.5: IF 热重载导致策略状态不一致, THEN THE Strategy_Lab SHALL 
           提示用户并提供"回滚到重载前状态"选项
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import inspect
import logging
import sys
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

from core.exceptions import StrategyError, ErrorCodes


logger = logging.getLogger(__name__)


class HotReloadPolicy(Enum):
    """
    Hot reload policy enumeration.
    
    Defines how strategy state is handled during hot reload:
    - RESET: Reset all variables to initial values
    - PRESERVE: Preserve all state variables
    - SELECTIVE: Preserve only @preserve decorated variables
    """
    RESET = "reset"
    PRESERVE = "preserve"
    SELECTIVE = "selective"


class ParameterType(Enum):
    """
    Strategy parameter type enumeration.
    
    Defines the type of parameter for UI widget mapping:
    - INT: Integer parameter (slider or input)
    - FLOAT: Float parameter (slider or input)
    - STRING: String parameter (text input)
    - BOOL: Boolean parameter (checkbox)
    - ENUM: Enumeration parameter (dropdown)
    """
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    BOOL = "bool"
    ENUM = "enum"


class UIWidget(Enum):
    """
    UI widget type enumeration.
    
    Defines the UI widget to use for parameter input:
    - INPUT: Text/number input field
    - SLIDER: Numeric slider
    - DROPDOWN: Dropdown selection
    - CHECKBOX: Boolean checkbox
    """
    INPUT = "input"
    SLIDER = "slider"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"


@dataclass
class StrategyParameter:
    """
    Strategy parameter definition.
    
    Captures the complete definition of a strategy parameter including
    type, constraints, and UI widget mapping.
    
    Attributes:
        name: Parameter name
        param_type: Parameter type (int, float, string, bool, enum)
        default_value: Default value for the parameter
        min_value: Minimum value (for numeric types)
        max_value: Maximum value (for numeric types)
        step: Step size for slider (for numeric types)
        options: List of options (for enum type)
        ui_widget: UI widget type for rendering
        description: Human-readable description
    """
    name: str
    param_type: ParameterType
    default_value: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    options: Optional[List[Any]] = None
    ui_widget: UIWidget = UIWidget.INPUT
    description: str = ""
    
    def __post_init__(self) -> None:
        """Validate parameter definition."""
        if not self.name:
            raise ValueError("Parameter name must not be empty")
        
        # Auto-determine UI widget if not specified
        if self.ui_widget == UIWidget.INPUT:
            if self.param_type == ParameterType.BOOL:
                self.ui_widget = UIWidget.CHECKBOX
            elif self.param_type == ParameterType.ENUM:
                self.ui_widget = UIWidget.DROPDOWN
            elif self.options is not None and len(self.options) > 0:
                # Has options list - use dropdown
                self.ui_widget = UIWidget.DROPDOWN
            elif self.param_type in (ParameterType.INT, ParameterType.FLOAT):
                if self.min_value is not None and self.max_value is not None:
                    self.ui_widget = UIWidget.SLIDER
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "name": self.name,
            "param_type": self.param_type.value,
            "default_value": self.default_value,
            "ui_widget": self.ui_widget.value,
            "description": self.description,
        }
        if self.min_value is not None:
            result["min_value"] = self.min_value
        if self.max_value is not None:
            result["max_value"] = self.max_value
        if self.step is not None:
            result["step"] = self.step
        if self.options is not None:
            result["options"] = self.options
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrategyParameter:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            param_type=ParameterType(data["param_type"]),
            default_value=data["default_value"],
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            step=data.get("step"),
            options=data.get("options"),
            ui_widget=UIWidget(data.get("ui_widget", "input")),
            description=data.get("description", ""),
        )


@dataclass
class ReloadResult:
    """
    Result of a hot reload operation.
    
    Captures the outcome of a hot reload including which variables
    were preserved and which were reset.
    
    Attributes:
        success: Whether the reload was successful
        policy: The reload policy that was applied
        preserved_variables: List of variable names that were preserved
        reset_variables: List of variable names that were reset
        error_message: Error message if reload failed
        timestamp: When the reload occurred
    """
    success: bool
    policy: HotReloadPolicy
    preserved_variables: List[str] = field(default_factory=list)
    reset_variables: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "policy": self.policy.value,
            "preserved_variables": self.preserved_variables,
            "reset_variables": self.reset_variables,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StrategyInfo:
    """
    Information about a loaded strategy.
    
    Attributes:
        strategy_id: Unique identifier for the strategy instance
        class_name: Name of the strategy class
        file_path: Path to the strategy file
        parameters: List of parameter definitions
        checksum: File checksum for change detection
        loaded_at: When the strategy was loaded
        is_active: Whether the strategy is currently active
    """
    strategy_id: str
    class_name: str
    file_path: str
    parameters: List[StrategyParameter]
    checksum: str
    loaded_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy_id": self.strategy_id,
            "class_name": self.class_name,
            "file_path": self.file_path,
            "parameters": [p.to_dict() for p in self.parameters],
            "checksum": self.checksum,
            "loaded_at": self.loaded_at.isoformat(),
            "is_active": self.is_active,
        }


# Decorator for marking variables to preserve during selective reload
def preserve(func_or_var: Any) -> Any:
    """
    Decorator to mark a variable or method for preservation during hot reload.
    
    When using SELECTIVE hot reload policy, only variables and methods
    marked with @preserve will retain their values.
    
    Example:
        class MyStrategy(CtaTemplate):
            @preserve
            def __init__(self):
                self.position = 0  # Will be preserved
                self.temp_data = []  # Will be reset
    """
    if callable(func_or_var):
        func_or_var._preserve = True
        return func_or_var
    return func_or_var


def _compute_file_checksum(file_path: str) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


class ParameterExtractor:
    """
    Extracts parameter definitions from strategy classes.
    
    Analyzes strategy class definitions to extract parameter information
    including types, default values, and constraints for UI mapping.
    """
    
    # Parameters to exclude (base class parameters)
    EXCLUDED_PARAMS = {'self', 'args', 'kwargs', 'strategy_name', 'symbols'}
    
    @staticmethod
    def extract_from_class(strategy_class: Type) -> List[StrategyParameter]:
        """
        Extract parameters from a strategy class.
        
        Looks for a 'parameters' class attribute that defines the
        strategy parameters. Supports various definition formats.
        
        Args:
            strategy_class: The strategy class to analyze.
        
        Returns:
            List of StrategyParameter definitions.
        """
        parameters: List[StrategyParameter] = []
        
        # Check for 'parameters' class attribute
        if hasattr(strategy_class, 'parameters'):
            params_def = getattr(strategy_class, 'parameters')
            
            if isinstance(params_def, dict):
                parameters = ParameterExtractor._parse_dict_params(params_def)
            elif isinstance(params_def, list):
                parameters = ParameterExtractor._parse_list_params(params_def)
        
        # Only use __init__ params if no explicit parameters defined
        # This avoids including base class parameters like strategy_name, symbols
        
        return parameters
    
    @staticmethod
    def _parse_dict_params(params_def: Dict[str, Any]) -> List[StrategyParameter]:
        """Parse parameters from dictionary format."""
        parameters = []
        
        for name, value in params_def.items():
            if isinstance(value, dict):
                # Extended format: {"fast_period": {"default": 10, "min": 1, "max": 100}}
                param = ParameterExtractor._parse_extended_param(name, value)
            else:
                # Simple format: {"fast_period": 10}
                param = ParameterExtractor._infer_param_from_value(name, value)
            
            parameters.append(param)
        
        return parameters
    
    @staticmethod
    def _parse_list_params(params_def: List[Any]) -> List[StrategyParameter]:
        """Parse parameters from list format."""
        parameters = []
        
        for item in params_def:
            if isinstance(item, dict) and "name" in item:
                param = StrategyParameter.from_dict(item)
                parameters.append(param)
            elif isinstance(item, StrategyParameter):
                parameters.append(item)
        
        return parameters
    
    @staticmethod
    def _parse_extended_param(name: str, config: Dict[str, Any]) -> StrategyParameter:
        """Parse extended parameter configuration."""
        default_value = config.get("default", config.get("value", 0))
        
        # Infer type from default value
        param_type = ParameterExtractor._infer_type(default_value)
        if "type" in config:
            param_type = ParameterType(config["type"])
        
        return StrategyParameter(
            name=name,
            param_type=param_type,
            default_value=default_value,
            min_value=config.get("min"),
            max_value=config.get("max"),
            step=config.get("step"),
            options=config.get("options"),
            ui_widget=UIWidget(config.get("widget", "input")),
            description=config.get("description", ""),
        )
    
    @staticmethod
    def _infer_param_from_value(name: str, value: Any) -> StrategyParameter:
        """Infer parameter definition from a simple value."""
        param_type = ParameterExtractor._infer_type(value)
        
        return StrategyParameter(
            name=name,
            param_type=param_type,
            default_value=value,
        )
    
    @staticmethod
    def _infer_type(value: Any) -> ParameterType:
        """Infer parameter type from value."""
        if isinstance(value, bool):
            return ParameterType.BOOL
        elif isinstance(value, int):
            return ParameterType.INT
        elif isinstance(value, float):
            return ParameterType.FLOAT
        elif isinstance(value, str):
            return ParameterType.STRING
        elif isinstance(value, (list, tuple)) and len(value) > 0:
            return ParameterType.ENUM
        else:
            return ParameterType.STRING
    
    @staticmethod
    def _extract_from_init(strategy_class: Type) -> List[StrategyParameter]:
        """Extract parameters from __init__ method signature."""
        parameters = []
        
        try:
            sig = inspect.signature(strategy_class.__init__)
            for name, param in sig.parameters.items():
                if name in ('self', 'args', 'kwargs'):
                    continue
                
                default_value = None
                if param.default != inspect.Parameter.empty:
                    default_value = param.default
                
                param_type = ParameterType.STRING
                if param.annotation != inspect.Parameter.empty:
                    param_type = ParameterExtractor._annotation_to_type(param.annotation)
                elif default_value is not None:
                    param_type = ParameterExtractor._infer_type(default_value)
                
                parameters.append(StrategyParameter(
                    name=name,
                    param_type=param_type,
                    default_value=default_value,
                ))
        except (ValueError, TypeError):
            pass
        
        return parameters
    
    @staticmethod
    def _annotation_to_type(annotation: Any) -> ParameterType:
        """Convert type annotation to ParameterType."""
        if annotation == int:
            return ParameterType.INT
        elif annotation == float:
            return ParameterType.FLOAT
        elif annotation == str:
            return ParameterType.STRING
        elif annotation == bool:
            return ParameterType.BOOL
        else:
            return ParameterType.STRING


class IStrategyManager(ABC):
    """
    Abstract interface for the Strategy Manager.
    
    The Strategy Manager is responsible for loading, managing, and
    hot-reloading trading strategies.
    """
    
    @abstractmethod
    def load_strategy_file(self, file_path: str) -> StrategyInfo:
        """
        Load a strategy from a Python file.
        
        Args:
            file_path: Path to the strategy Python file.
        
        Returns:
            StrategyInfo with loaded strategy details.
        
        Raises:
            StrategyError: If loading fails.
        """
        pass
    
    @abstractmethod
    def get_parameters(self, strategy_id: str) -> List[StrategyParameter]:
        """
        Get parameter definitions for a strategy.
        
        Args:
            strategy_id: The strategy identifier.
        
        Returns:
            List of parameter definitions.
        """
        pass
    
    @abstractmethod
    def set_parameters(self, strategy_id: str, params: Dict[str, Any]) -> bool:
        """
        Set parameter values for a strategy.
        
        Args:
            strategy_id: The strategy identifier.
            params: Dictionary of parameter name to value.
        
        Returns:
            True if parameters were set successfully.
        """
        pass
    
    @abstractmethod
    def hot_reload(
        self,
        strategy_id: str,
        policy: HotReloadPolicy,
        preserve_vars: Optional[Set[str]] = None,
    ) -> ReloadResult:
        """
        Hot reload a strategy with the specified policy.
        
        Args:
            strategy_id: The strategy identifier.
            policy: The hot reload policy to apply.
            preserve_vars: Set of variable names to preserve (for SELECTIVE).
        
        Returns:
            ReloadResult with details of the reload operation.
        """
        pass
    
    @abstractmethod
    def rollback(self, strategy_id: str) -> bool:
        """
        Rollback to the state before the last hot reload.
        
        Args:
            strategy_id: The strategy identifier.
        
        Returns:
            True if rollback was successful.
        """
        pass
    
    @abstractmethod
    def get_state_variables(self, strategy_id: str) -> Dict[str, Any]:
        """
        Get all state variables for a strategy.
        
        Args:
            strategy_id: The strategy identifier.
        
        Returns:
            Dictionary of variable name to value.
        """
        pass
    
    @abstractmethod
    def get_strategy_info(self, strategy_id: str) -> Optional[StrategyInfo]:
        """
        Get information about a loaded strategy.
        
        Args:
            strategy_id: The strategy identifier.
        
        Returns:
            StrategyInfo or None if not found.
        """
        pass
    
    @abstractmethod
    def list_strategies(self) -> List[StrategyInfo]:
        """
        List all loaded strategies.
        
        Returns:
            List of StrategyInfo for all loaded strategies.
        """
        pass


class StrategyManager(IStrategyManager):
    """
    Implementation of the Strategy Manager.
    
    Provides functionality for loading, managing, and hot-reloading
    trading strategies with support for multiple reload policies.
    
    Example:
        >>> manager = StrategyManager()
        >>> info = manager.load_strategy_file("strategies/ma_cross.py")
        >>> params = manager.get_parameters(info.strategy_id)
        >>> manager.set_parameters(info.strategy_id, {"fast_period": 5})
        >>> result = manager.hot_reload(info.strategy_id, HotReloadPolicy.PRESERVE)
    """
    
    def __init__(self) -> None:
        """Initialize the Strategy Manager."""
        # Loaded strategies: strategy_id -> StrategyInfo
        self._strategies: Dict[str, StrategyInfo] = {}
        
        # Strategy instances: strategy_id -> instance
        self._instances: Dict[str, Any] = {}
        
        # Strategy classes: strategy_id -> class
        self._classes: Dict[str, Type] = {}
        
        # Current parameter values: strategy_id -> {param_name: value}
        self._current_params: Dict[str, Dict[str, Any]] = {}
        
        # State snapshots for rollback: strategy_id -> state_dict
        self._rollback_states: Dict[str, Dict[str, Any]] = {}
        
        # Reload history: strategy_id -> List[ReloadResult]
        self._reload_history: Dict[str, List[ReloadResult]] = {}
    
    def load_strategy_file(self, file_path: str) -> StrategyInfo:
        """
        Load a strategy from a Python file.
        
        Args:
            file_path: Path to the strategy Python file.
        
        Returns:
            StrategyInfo with loaded strategy details.
        
        Raises:
            StrategyError: If loading fails.
        """
        path = Path(file_path)
        
        if not path.exists():
            raise StrategyError(
                message=f"Strategy file not found: {file_path}",
                error_code=ErrorCodes.STRATEGY_NOT_FOUND,
                strategy_name=path.stem,
            )
        
        if not path.suffix == ".py":
            raise StrategyError(
                message=f"Invalid strategy file type: {path.suffix}",
                error_code=ErrorCodes.STRATEGY_LOAD_FAILED,
                strategy_name=path.stem,
            )
        
        try:
            # Compute file checksum
            checksum = _compute_file_checksum(file_path)
            
            # Load the module
            module_name = f"strategy_{path.stem}_{uuid.uuid4().hex[:8]}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                raise StrategyError(
                    message=f"Failed to create module spec for: {file_path}",
                    error_code=ErrorCodes.STRATEGY_LOAD_FAILED,
                )
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Find strategy class (look for class inheriting from CtaTemplate or similar)
            strategy_class = self._find_strategy_class(module)
            if strategy_class is None:
                raise StrategyError(
                    message=f"No strategy class found in: {file_path}",
                    error_code=ErrorCodes.STRATEGY_LOAD_FAILED,
                )
            
            # Extract parameters
            parameters = ParameterExtractor.extract_from_class(strategy_class)
            
            # Generate strategy ID
            strategy_id = str(uuid.uuid4())
            
            # Create strategy info
            info = StrategyInfo(
                strategy_id=strategy_id,
                class_name=strategy_class.__name__,
                file_path=str(path.absolute()),
                parameters=parameters,
                checksum=checksum,
            )
            
            # Store strategy
            self._strategies[strategy_id] = info
            self._classes[strategy_id] = strategy_class
            self._current_params[strategy_id] = {
                p.name: p.default_value for p in parameters
            }
            self._reload_history[strategy_id] = []
            
            logger.info(f"Loaded strategy: {info.class_name} ({strategy_id})")
            
            return info
            
        except StrategyError:
            raise
        except Exception as e:
            raise StrategyError(
                message=f"Failed to load strategy: {e}",
                error_code=ErrorCodes.STRATEGY_LOAD_FAILED,
                strategy_name=path.stem,
                details={"error": str(e)},
            )
    
    def _find_strategy_class(self, module: Any) -> Optional[Type]:
        """Find the strategy class in a module."""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # Skip imported classes
            if obj.__module__ != module.__name__:
                continue
            
            # Check for strategy indicators
            if hasattr(obj, 'parameters') or hasattr(obj, 'on_bar') or hasattr(obj, 'on_tick'):
                return obj
            
            # Check class name patterns
            if 'Strategy' in name or 'Template' in name:
                return obj
        
        return None
    
    def get_parameters(self, strategy_id: str) -> List[StrategyParameter]:
        """Get parameter definitions for a strategy."""
        if strategy_id not in self._strategies:
            raise StrategyError(
                message=f"Strategy not found: {strategy_id}",
                error_code=ErrorCodes.STRATEGY_NOT_FOUND,
                strategy_id=strategy_id,
            )
        
        return self._strategies[strategy_id].parameters
    
    def set_parameters(self, strategy_id: str, params: Dict[str, Any]) -> bool:
        """Set parameter values for a strategy."""
        if strategy_id not in self._strategies:
            raise StrategyError(
                message=f"Strategy not found: {strategy_id}",
                error_code=ErrorCodes.STRATEGY_NOT_FOUND,
                strategy_id=strategy_id,
            )
        
        # Validate parameters
        valid_params = {p.name for p in self._strategies[strategy_id].parameters}
        for name in params:
            if name not in valid_params:
                raise StrategyError(
                    message=f"Invalid parameter: {name}",
                    error_code=ErrorCodes.STRATEGY_PARAM_INVALID,
                    strategy_id=strategy_id,
                    details={"parameter": name, "valid_parameters": list(valid_params)},
                )
        
        # Update parameters
        self._current_params[strategy_id].update(params)
        
        # Update instance if exists
        if strategy_id in self._instances:
            instance = self._instances[strategy_id]
            for name, value in params.items():
                if hasattr(instance, name):
                    setattr(instance, name, value)
        
        logger.info(f"Updated parameters for strategy {strategy_id}: {params}")
        return True
    
    def hot_reload(
        self,
        strategy_id: str,
        policy: HotReloadPolicy,
        preserve_vars: Optional[Set[str]] = None,
    ) -> ReloadResult:
        """Hot reload a strategy with the specified policy."""
        if strategy_id not in self._strategies:
            return ReloadResult(
                success=False,
                policy=policy,
                error_message=f"Strategy not found: {strategy_id}",
            )
        
        info = self._strategies[strategy_id]
        
        try:
            # Save current state for rollback
            if strategy_id in self._instances:
                self._rollback_states[strategy_id] = self._capture_state(strategy_id)
            
            # Reload the module
            checksum = _compute_file_checksum(info.file_path)
            
            module_name = f"strategy_{Path(info.file_path).stem}_{uuid.uuid4().hex[:8]}"
            spec = importlib.util.spec_from_file_location(module_name, info.file_path)
            if spec is None or spec.loader is None:
                raise StrategyError(
                    message="Failed to create module spec",
                    error_code=ErrorCodes.HOT_RELOAD_FAILED,
                )
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Find new strategy class
            new_class = self._find_strategy_class(module)
            if new_class is None:
                raise StrategyError(
                    message="No strategy class found after reload",
                    error_code=ErrorCodes.HOT_RELOAD_FAILED,
                )
            
            # Extract new parameters
            new_parameters = ParameterExtractor.extract_from_class(new_class)
            
            # Apply reload policy
            preserved_vars: List[str] = []
            reset_vars: List[str] = []
            
            if strategy_id in self._instances:
                old_instance = self._instances[strategy_id]
                old_state = self._get_instance_state(old_instance)
                
                # Create new instance
                new_instance = new_class()
                
                # Apply policy
                if policy == HotReloadPolicy.RESET:
                    # Reset all - just use new instance
                    reset_vars = list(old_state.keys())
                    
                elif policy == HotReloadPolicy.PRESERVE:
                    # Preserve all state variables
                    for name, value in old_state.items():
                        if hasattr(new_instance, name):
                            try:
                                setattr(new_instance, name, value)
                                preserved_vars.append(name)
                            except Exception:
                                reset_vars.append(name)
                        else:
                            reset_vars.append(name)
                    
                elif policy == HotReloadPolicy.SELECTIVE:
                    # Preserve only specified or @preserve decorated variables
                    preserve_set = preserve_vars or set()
                    
                    # Add @preserve decorated variables
                    for name in dir(old_instance):
                        if name.startswith('_'):
                            continue
                        attr = getattr(old_instance, name, None)
                        if callable(attr) and getattr(attr, '_preserve', False):
                            preserve_set.add(name)
                    
                    for name, value in old_state.items():
                        if name in preserve_set and hasattr(new_instance, name):
                            try:
                                setattr(new_instance, name, value)
                                preserved_vars.append(name)
                            except Exception:
                                reset_vars.append(name)
                        else:
                            reset_vars.append(name)
                
                self._instances[strategy_id] = new_instance
            
            # Update stored info
            self._classes[strategy_id] = new_class
            info.checksum = checksum
            info.parameters = new_parameters
            
            result = ReloadResult(
                success=True,
                policy=policy,
                preserved_variables=preserved_vars,
                reset_variables=reset_vars,
            )
            
            self._reload_history[strategy_id].append(result)
            
            logger.info(
                f"Hot reload successful for {strategy_id}: "
                f"policy={policy.value}, preserved={len(preserved_vars)}, reset={len(reset_vars)}"
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Hot reload failed for {strategy_id}: {error_msg}")
            
            result = ReloadResult(
                success=False,
                policy=policy,
                error_message=error_msg,
            )
            self._reload_history[strategy_id].append(result)
            
            return result
    
    def _capture_state(self, strategy_id: str) -> Dict[str, Any]:
        """Capture the current state of a strategy instance."""
        if strategy_id not in self._instances:
            return {}
        
        instance = self._instances[strategy_id]
        return copy.deepcopy(self._get_instance_state(instance))
    
    def _get_instance_state(self, instance: Any) -> Dict[str, Any]:
        """Get state variables from an instance."""
        state = {}
        for name in dir(instance):
            if name.startswith('_'):
                continue
            try:
                value = getattr(instance, name)
                if not callable(value):
                    state[name] = value
            except Exception:
                pass
        return state
    
    def rollback(self, strategy_id: str) -> bool:
        """Rollback to the state before the last hot reload."""
        if strategy_id not in self._rollback_states:
            logger.warning(f"No rollback state available for {strategy_id}")
            return False
        
        if strategy_id not in self._instances:
            logger.warning(f"No instance to rollback for {strategy_id}")
            return False
        
        try:
            saved_state = self._rollback_states[strategy_id]
            instance = self._instances[strategy_id]
            
            for name, value in saved_state.items():
                if hasattr(instance, name):
                    setattr(instance, name, value)
            
            logger.info(f"Rollback successful for {strategy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed for {strategy_id}: {e}")
            return False
    
    def get_state_variables(self, strategy_id: str) -> Dict[str, Any]:
        """Get all state variables for a strategy."""
        if strategy_id not in self._instances:
            return {}
        
        return self._get_instance_state(self._instances[strategy_id])
    
    def get_strategy_info(self, strategy_id: str) -> Optional[StrategyInfo]:
        """Get information about a loaded strategy."""
        return self._strategies.get(strategy_id)
    
    def list_strategies(self) -> List[StrategyInfo]:
        """List all loaded strategies."""
        return list(self._strategies.values())
    
    def create_instance(self, strategy_id: str, **kwargs: Any) -> Any:
        """
        Create an instance of a loaded strategy.
        
        Args:
            strategy_id: The strategy identifier.
            **kwargs: Additional arguments for the strategy constructor.
        
        Returns:
            The strategy instance.
        """
        if strategy_id not in self._classes:
            raise StrategyError(
                message=f"Strategy not found: {strategy_id}",
                error_code=ErrorCodes.STRATEGY_NOT_FOUND,
                strategy_id=strategy_id,
            )
        
        strategy_class = self._classes[strategy_id]
        params = self._current_params.get(strategy_id, {})
        
        # Merge with kwargs
        all_params = {**params, **kwargs}
        
        # Create instance
        instance = strategy_class(**all_params)
        self._instances[strategy_id] = instance
        
        return instance
    
    def get_reload_history(self, strategy_id: str) -> List[ReloadResult]:
        """Get the reload history for a strategy."""
        return self._reload_history.get(strategy_id, [])


__all__ = [
    "HotReloadPolicy",
    "ParameterType",
    "UIWidget",
    "StrategyParameter",
    "ReloadResult",
    "StrategyInfo",
    "preserve",
    "ParameterExtractor",
    "IStrategyManager",
    "StrategyManager",
]
