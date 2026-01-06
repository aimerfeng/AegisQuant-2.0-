"""
Titan-Quant Parameter Optimizer

This module implements the parameter optimization functionality using Optuna
for intelligent parameter search with support for Bayesian optimization and
genetic algorithms.

Requirements:
    - 9.1: THE Optimizer SHALL 集成 Optuna，支持贝叶斯优化和遗传算法
    - 9.2: WHEN 用户选择参数范围和优化目标, THEN THE Optimizer SHALL 
           自动搜索最优参数组合
    - 9.3: THE Optimizer SHALL 支持 Sharpe Ratio、Total Return 等多种优化目标
    - 9.5: THE Optimization_Mode SHALL 采用多进程并行执行，每个进程拥有独立的
           策略实例和数据副本
    - 9.6: THE Optimization_Mode SHALL 保证进程间完全隔离，一个进程的崩溃不影响
           其他进程
"""
from __future__ import annotations

import logging
import multiprocessing as mp
import os
import traceback
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

import optuna
from optuna.samplers import TPESampler, CmaEsSampler, NSGAIISampler

from core.exceptions import TitanQuantError, ErrorCodes


logger = logging.getLogger(__name__)


class OptimizerError(TitanQuantError):
    """Exception raised for optimizer-related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        optimization_id: str | None = None,
    ) -> None:
        details = details or {}
        if optimization_id:
            details["optimization_id"] = optimization_id
        super().__init__(message, error_code, details)
        self.optimization_id = optimization_id


class OptimizationObjective(Enum):
    """
    Optimization objective enumeration.
    
    Defines the metric to optimize during parameter search:
    - SHARPE_RATIO: Maximize risk-adjusted returns
    - TOTAL_RETURN: Maximize total returns
    - MAX_DRAWDOWN: Minimize maximum drawdown
    - WIN_RATE: Maximize win rate
    - PROFIT_FACTOR: Maximize profit factor
    - CALMAR_RATIO: Maximize Calmar ratio (return / max drawdown)
    - SORTINO_RATIO: Maximize Sortino ratio (downside risk-adjusted)
    """
    SHARPE_RATIO = "sharpe_ratio"
    TOTAL_RETURN = "total_return"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    CALMAR_RATIO = "calmar_ratio"
    SORTINO_RATIO = "sortino_ratio"


class OptimizationAlgorithm(Enum):
    """
    Optimization algorithm enumeration.
    
    Defines the search algorithm to use:
    - TPE: Tree-structured Parzen Estimator (Bayesian optimization)
    - CMA_ES: Covariance Matrix Adaptation Evolution Strategy
    - NSGA_II: Non-dominated Sorting Genetic Algorithm II (multi-objective)
    - GRID: Grid search (exhaustive)
    - RANDOM: Random search
    """
    TPE = "tpe"
    CMA_ES = "cma_es"
    NSGA_II = "nsga_ii"
    GRID = "grid"
    RANDOM = "random"


class ParameterType(Enum):
    """Parameter type for optimization."""
    INT = "int"
    FLOAT = "float"
    CATEGORICAL = "categorical"
    LOG_FLOAT = "log_float"  # Log-uniform distribution


@dataclass
class ParameterRange:
    """
    Definition of a parameter range for optimization.
    
    Attributes:
        name: Parameter name
        param_type: Type of parameter (int, float, categorical, log_float)
        low: Lower bound (for numeric types)
        high: Upper bound (for numeric types)
        step: Step size (optional, for int/float)
        choices: List of choices (for categorical type)
        log: Whether to use log scale (for float type)
    """
    name: str
    param_type: ParameterType
    low: Optional[float] = None
    high: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[List[Any]] = None
    log: bool = False
    
    def __post_init__(self) -> None:
        """Validate parameter range definition."""
        if not self.name:
            raise ValueError("Parameter name must not be empty")
        
        if self.param_type in (ParameterType.INT, ParameterType.FLOAT, ParameterType.LOG_FLOAT):
            if self.low is None or self.high is None:
                raise ValueError(f"Numeric parameter '{self.name}' requires low and high bounds")
            if self.low >= self.high:
                raise ValueError(f"Parameter '{self.name}': low must be less than high")
        
        if self.param_type == ParameterType.CATEGORICAL:
            if not self.choices or len(self.choices) == 0:
                raise ValueError(f"Categorical parameter '{self.name}' requires choices")
    
    def suggest(self, trial: optuna.Trial) -> Any:
        """
        Suggest a value for this parameter using Optuna trial.
        
        Args:
            trial: Optuna trial object
        
        Returns:
            Suggested parameter value
        """
        if self.param_type == ParameterType.INT:
            return trial.suggest_int(
                self.name,
                int(self.low),
                int(self.high),
                step=int(self.step) if self.step else 1,
            )
        elif self.param_type == ParameterType.FLOAT:
            if self.step:
                return trial.suggest_float(
                    self.name,
                    self.low,
                    self.high,
                    step=self.step,
                )
            else:
                return trial.suggest_float(
                    self.name,
                    self.low,
                    self.high,
                )
        elif self.param_type == ParameterType.LOG_FLOAT:
            return trial.suggest_float(
                self.name,
                self.low,
                self.high,
                log=True,
            )
        elif self.param_type == ParameterType.CATEGORICAL:
            return trial.suggest_categorical(self.name, self.choices)
        else:
            raise ValueError(f"Unknown parameter type: {self.param_type}")
    
    def validate_value(self, value: Any) -> bool:
        """
        Validate that a value is within the parameter range.
        
        Args:
            value: Value to validate
        
        Returns:
            True if value is within bounds
        """
        if self.param_type in (ParameterType.INT, ParameterType.FLOAT, ParameterType.LOG_FLOAT):
            if value < self.low or value > self.high:
                return False
            if self.param_type == ParameterType.INT and not isinstance(value, int):
                # Allow float that is effectively an int
                if value != int(value):
                    return False
        elif self.param_type == ParameterType.CATEGORICAL:
            if value not in self.choices:
                return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "name": self.name,
            "param_type": self.param_type.value,
        }
        if self.low is not None:
            result["low"] = self.low
        if self.high is not None:
            result["high"] = self.high
        if self.step is not None:
            result["step"] = self.step
        if self.choices is not None:
            result["choices"] = self.choices
        if self.log:
            result["log"] = self.log
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ParameterRange:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            param_type=ParameterType(data["param_type"]),
            low=data.get("low"),
            high=data.get("high"),
            step=data.get("step"),
            choices=data.get("choices"),
            log=data.get("log", False),
        )


@dataclass
class OptimizationConfig:
    """
    Configuration for an optimization run.
    
    Attributes:
        parameter_ranges: List of parameter ranges to optimize
        objective: Optimization objective (metric to optimize)
        algorithm: Optimization algorithm to use
        n_trials: Number of optimization trials
        n_jobs: Number of parallel jobs (-1 for all CPUs)
        timeout: Maximum time in seconds (None for no limit)
        direction: Optimization direction ("maximize" or "minimize")
        seed: Random seed for reproducibility
        study_name: Name for the Optuna study
        storage: Optuna storage URL (None for in-memory)
    """
    parameter_ranges: List[ParameterRange]
    objective: OptimizationObjective = OptimizationObjective.SHARPE_RATIO
    algorithm: OptimizationAlgorithm = OptimizationAlgorithm.TPE
    n_trials: int = 100
    n_jobs: int = 1
    timeout: Optional[float] = None
    direction: str = "maximize"
    seed: Optional[int] = None
    study_name: Optional[str] = None
    storage: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.parameter_ranges:
            raise ValueError("At least one parameter range is required")
        
        if self.n_trials < 1:
            raise ValueError("n_trials must be at least 1")
        
        if self.direction not in ("maximize", "minimize"):
            raise ValueError("direction must be 'maximize' or 'minimize'")
        
        # Set default direction based on objective
        if self.objective == OptimizationObjective.MAX_DRAWDOWN:
            self.direction = "minimize"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "parameter_ranges": [p.to_dict() for p in self.parameter_ranges],
            "objective": self.objective.value,
            "algorithm": self.algorithm.value,
            "n_trials": self.n_trials,
            "n_jobs": self.n_jobs,
            "timeout": self.timeout,
            "direction": self.direction,
            "seed": self.seed,
            "study_name": self.study_name,
            "storage": self.storage,
        }


@dataclass
class OptimizationResult:
    """
    Result of a single optimization trial.
    
    Attributes:
        trial_number: Trial number
        params: Parameter values used
        value: Objective value achieved
        metrics: Additional metrics from the backtest
        duration: Trial duration in seconds
        status: Trial status (complete, pruned, failed)
        error_message: Error message if failed
    """
    trial_number: int
    params: Dict[str, Any]
    value: Optional[float]
    metrics: Dict[str, float] = field(default_factory=dict)
    duration: float = 0.0
    status: str = "complete"
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trial_number": self.trial_number,
            "params": self.params,
            "value": self.value,
            "metrics": self.metrics,
            "duration": self.duration,
            "status": self.status,
            "error_message": self.error_message,
        }



@dataclass
class OptimizationSummary:
    """
    Summary of an optimization run.
    
    Attributes:
        optimization_id: Unique identifier for the optimization
        config: Optimization configuration used
        best_params: Best parameter values found
        best_value: Best objective value achieved
        best_metrics: Metrics from the best trial
        all_results: All trial results
        total_trials: Total number of trials completed
        successful_trials: Number of successful trials
        failed_trials: Number of failed trials
        start_time: When optimization started
        end_time: When optimization ended
        duration: Total duration in seconds
    """
    optimization_id: str
    config: OptimizationConfig
    best_params: Dict[str, Any]
    best_value: Optional[float]
    best_metrics: Dict[str, float] = field(default_factory=dict)
    all_results: List[OptimizationResult] = field(default_factory=list)
    total_trials: int = 0
    successful_trials: int = 0
    failed_trials: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "optimization_id": self.optimization_id,
            "config": self.config.to_dict(),
            "best_params": self.best_params,
            "best_value": self.best_value,
            "best_metrics": self.best_metrics,
            "all_results": [r.to_dict() for r in self.all_results],
            "total_trials": self.total_trials,
            "successful_trials": self.successful_trials,
            "failed_trials": self.failed_trials,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
        }


# Type alias for objective function
ObjectiveFunction = Callable[[Dict[str, Any]], Tuple[float, Dict[str, float]]]


class IOptimizer(ABC):
    """
    Abstract interface for the Parameter Optimizer.
    
    The Optimizer is responsible for searching the parameter space
    to find optimal strategy parameters.
    """
    
    @abstractmethod
    def optimize(
        self,
        objective_func: ObjectiveFunction,
        config: OptimizationConfig,
        callback: Optional[Callable[[OptimizationResult], None]] = None,
    ) -> OptimizationSummary:
        """
        Run parameter optimization.
        
        Args:
            objective_func: Function that takes parameters and returns
                           (objective_value, metrics_dict)
            config: Optimization configuration
            callback: Optional callback for each trial result
        
        Returns:
            OptimizationSummary with results
        """
        pass
    
    @abstractmethod
    def get_parameter_importance(self) -> Dict[str, float]:
        """
        Get parameter importance scores.
        
        Returns:
            Dictionary of parameter name to importance score
        """
        pass
    
    @abstractmethod
    def get_optimization_history(self) -> List[OptimizationResult]:
        """
        Get the history of all optimization trials.
        
        Returns:
            List of OptimizationResult for all trials
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the current optimization run."""
        pass


def _create_sampler(
    algorithm: OptimizationAlgorithm,
    seed: Optional[int] = None,
) -> optuna.samplers.BaseSampler:
    """
    Create an Optuna sampler based on the algorithm.
    
    Args:
        algorithm: Optimization algorithm
        seed: Random seed
    
    Returns:
        Optuna sampler instance
    """
    if algorithm == OptimizationAlgorithm.TPE:
        return TPESampler(seed=seed)
    elif algorithm == OptimizationAlgorithm.CMA_ES:
        return CmaEsSampler(seed=seed)
    elif algorithm == OptimizationAlgorithm.NSGA_II:
        return NSGAIISampler(seed=seed)
    elif algorithm == OptimizationAlgorithm.RANDOM:
        return optuna.samplers.RandomSampler(seed=seed)
    elif algorithm == OptimizationAlgorithm.GRID:
        # Grid sampler requires search_space, will be set later
        return optuna.samplers.RandomSampler(seed=seed)
    else:
        return TPESampler(seed=seed)


def _run_trial_in_process(
    objective_func: ObjectiveFunction,
    params: Dict[str, Any],
    trial_number: int,
) -> OptimizationResult:
    """
    Run a single trial in an isolated process.
    
    This function is designed to be called in a separate process
    for crash isolation. Each process has its own memory space,
    ensuring that crashes in one trial don't affect others.
    
    Args:
        objective_func: The objective function to evaluate
        params: Parameter values to test
        trial_number: Trial number
    
    Returns:
        OptimizationResult with trial outcome
    """
    import time
    import signal
    import sys
    
    start_time = time.time()
    
    # Set up signal handlers for graceful termination
    def signal_handler(signum, frame):
        raise KeyboardInterrupt("Process terminated by signal")
    
    # Only set signal handlers on Unix-like systems
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Isolate the execution - each process has independent state
        value, metrics = objective_func(params)
        duration = time.time() - start_time
        
        return OptimizationResult(
            trial_number=trial_number,
            params=params,
            value=value,
            metrics=metrics,
            duration=duration,
            status="complete",
        )
    except KeyboardInterrupt:
        duration = time.time() - start_time
        return OptimizationResult(
            trial_number=trial_number,
            params=params,
            value=None,
            duration=duration,
            status="cancelled",
            error_message="Process was cancelled",
        )
    except Exception as e:
        duration = time.time() - start_time
        error_tb = traceback.format_exc()
        return OptimizationResult(
            trial_number=trial_number,
            params=params,
            value=None,
            duration=duration,
            status="failed",
            error_message=f"{str(e)}\n{error_tb}",
        )


class ProcessIsolatedOptimizer:
    """
    Process-isolated optimizer for crash-safe parallel optimization.
    
    This class provides enhanced process isolation where each optimization
    trial runs in a completely separate process with its own memory space.
    If a trial crashes (e.g., segfault, out of memory), it doesn't affect
    other running trials or the main optimization process.
    
    Features:
        - Complete process isolation for each trial
        - Automatic crash recovery
        - Timeout handling per trial
        - Resource cleanup on failure
    
    Example:
        >>> optimizer = ProcessIsolatedOptimizer(max_workers=4)
        >>> results = optimizer.run_trials(objective_func, param_sets)
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        trial_timeout: Optional[float] = None,
    ) -> None:
        """
        Initialize the process-isolated optimizer.
        
        Args:
            max_workers: Maximum number of parallel processes
            trial_timeout: Timeout in seconds for each trial (None for no limit)
        """
        self.max_workers = max_workers if max_workers > 0 else mp.cpu_count()
        self.trial_timeout = trial_timeout
        self._executor: Optional[ProcessPoolExecutor] = None
        self._is_running = False
    
    def run_trials(
        self,
        objective_func: ObjectiveFunction,
        param_sets: List[Tuple[int, Dict[str, Any]]],
        callback: Optional[Callable[[OptimizationResult], None]] = None,
    ) -> List[OptimizationResult]:
        """
        Run multiple trials in parallel with process isolation.
        
        Args:
            objective_func: The objective function to evaluate
            param_sets: List of (trial_number, params) tuples
            callback: Optional callback for each completed trial
        
        Returns:
            List of OptimizationResult for all trials
        """
        results = []
        self._is_running = True
        
        # Use spawn context for better isolation on all platforms
        ctx = mp.get_context('spawn')
        
        with ProcessPoolExecutor(
            max_workers=self.max_workers,
            mp_context=ctx,
        ) as executor:
            self._executor = executor
            
            # Submit all trials
            future_to_trial = {}
            for trial_number, params in param_sets:
                future = executor.submit(
                    _run_trial_in_process,
                    objective_func,
                    params,
                    trial_number,
                )
                future_to_trial[future] = (trial_number, params)
            
            # Collect results as they complete
            for future in as_completed(future_to_trial):
                trial_number, params = future_to_trial[future]
                
                try:
                    result = future.result(timeout=self.trial_timeout)
                except TimeoutError:
                    result = OptimizationResult(
                        trial_number=trial_number,
                        params=params,
                        value=None,
                        status="timeout",
                        error_message=f"Trial exceeded timeout of {self.trial_timeout}s",
                    )
                except Exception as e:
                    # Process crashed or other error
                    result = OptimizationResult(
                        trial_number=trial_number,
                        params=params,
                        value=None,
                        status="crashed",
                        error_message=f"Process crashed: {str(e)}",
                    )
                    logger.error(f"Trial {trial_number} process crashed: {e}")
                
                results.append(result)
                
                if callback:
                    callback(result)
        
        self._executor = None
        self._is_running = False
        
        return results
    
    def shutdown(self) -> None:
        """Shutdown the executor and terminate all running processes."""
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        self._is_running = False


class ParameterOptimizer(IOptimizer):
    """
    Implementation of the Parameter Optimizer using Optuna.
    
    Provides intelligent parameter search with support for:
    - Bayesian optimization (TPE)
    - Evolutionary algorithms (CMA-ES, NSGA-II)
    - Multi-process parallel execution with crash isolation
    
    Example:
        >>> optimizer = ParameterOptimizer()
        >>> config = OptimizationConfig(
        ...     parameter_ranges=[
        ...         ParameterRange("fast_period", ParameterType.INT, 5, 50),
        ...         ParameterRange("slow_period", ParameterType.INT, 20, 200),
        ...     ],
        ...     objective=OptimizationObjective.SHARPE_RATIO,
        ...     n_trials=100,
        ...     n_jobs=4,
        ... )
        >>> def objective(params):
        ...     # Run backtest with params
        ...     return sharpe_ratio, {"total_return": total_return}
        >>> summary = optimizer.optimize(objective, config)
    """
    
    def __init__(self) -> None:
        """Initialize the Parameter Optimizer."""
        self._study: Optional[optuna.Study] = None
        self._config: Optional[OptimizationConfig] = None
        self._results: List[OptimizationResult] = []
        self._is_running: bool = False
        self._should_stop: bool = False
        self._optimization_id: Optional[str] = None
    
    def optimize(
        self,
        objective_func: ObjectiveFunction,
        config: OptimizationConfig,
        callback: Optional[Callable[[OptimizationResult], None]] = None,
    ) -> OptimizationSummary:
        """
        Run parameter optimization.
        
        Args:
            objective_func: Function that takes parameters and returns
                           (objective_value, metrics_dict)
            config: Optimization configuration
            callback: Optional callback for each trial result
        
        Returns:
            OptimizationSummary with results
        """
        self._config = config
        self._results = []
        self._is_running = True
        self._should_stop = False
        self._optimization_id = str(uuid.uuid4())
        
        start_time = datetime.now()
        
        # Create sampler
        sampler = _create_sampler(config.algorithm, config.seed)
        
        # Create study
        study_name = config.study_name or f"optimization_{self._optimization_id}"
        
        self._study = optuna.create_study(
            study_name=study_name,
            direction=config.direction,
            sampler=sampler,
            storage=config.storage,
            load_if_exists=True,
        )
        
        # Create objective wrapper
        def optuna_objective(trial: optuna.Trial) -> float:
            if self._should_stop:
                raise optuna.TrialPruned()
            
            # Suggest parameters
            params = {}
            for param_range in config.parameter_ranges:
                params[param_range.name] = param_range.suggest(trial)
            
            # Run objective function
            trial_start = datetime.now()
            try:
                value, metrics = objective_func(params)
                duration = (datetime.now() - trial_start).total_seconds()
                
                result = OptimizationResult(
                    trial_number=trial.number,
                    params=params,
                    value=value,
                    metrics=metrics,
                    duration=duration,
                    status="complete",
                )
                
                # Store user attributes for later retrieval
                for key, val in metrics.items():
                    trial.set_user_attr(key, val)
                
            except Exception as e:
                duration = (datetime.now() - trial_start).total_seconds()
                result = OptimizationResult(
                    trial_number=trial.number,
                    params=params,
                    value=None,
                    duration=duration,
                    status="failed",
                    error_message=str(e),
                )
                logger.warning(f"Trial {trial.number} failed: {e}")
                raise optuna.TrialPruned()
            
            self._results.append(result)
            
            if callback:
                callback(result)
            
            return value
        
        # Run optimization
        try:
            if config.n_jobs == 1:
                # Single-threaded optimization
                self._study.optimize(
                    optuna_objective,
                    n_trials=config.n_trials,
                    timeout=config.timeout,
                    show_progress_bar=False,
                )
            else:
                # Multi-process optimization with crash isolation
                self._run_parallel_optimization(
                    objective_func,
                    config,
                    callback,
                )
        except KeyboardInterrupt:
            logger.info("Optimization interrupted by user")
        finally:
            self._is_running = False
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Build summary
        best_trial = self._study.best_trial if self._study.best_trial else None
        best_params = best_trial.params if best_trial else {}
        best_value = best_trial.value if best_trial else None
        best_metrics = dict(best_trial.user_attrs) if best_trial else {}
        
        successful = sum(1 for r in self._results if r.status == "complete")
        failed = sum(1 for r in self._results if r.status == "failed")
        
        summary = OptimizationSummary(
            optimization_id=self._optimization_id,
            config=config,
            best_params=best_params,
            best_value=best_value,
            best_metrics=best_metrics,
            all_results=self._results,
            total_trials=len(self._results),
            successful_trials=successful,
            failed_trials=failed,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
        )
        
        logger.info(
            f"Optimization complete: {successful}/{len(self._results)} trials successful, "
            f"best value: {best_value}"
        )
        
        return summary
    
    def _run_parallel_optimization(
        self,
        objective_func: ObjectiveFunction,
        config: OptimizationConfig,
        callback: Optional[Callable[[OptimizationResult], None]] = None,
    ) -> None:
        """
        Run optimization with multi-process parallelism.
        
        Each trial runs in an isolated process for crash isolation.
        This ensures that:
        - Each process has independent memory space
        - A crash in one trial doesn't affect others
        - Resources are properly cleaned up on failure
        
        Args:
            objective_func: The objective function
            config: Optimization configuration
            callback: Optional callback for each trial
        """
        n_jobs = config.n_jobs
        if n_jobs == -1:
            n_jobs = mp.cpu_count()
        
        # Use spawn context for better isolation
        ctx = mp.get_context('spawn')
        
        # Use ProcessPoolExecutor for crash isolation
        with ProcessPoolExecutor(max_workers=n_jobs, mp_context=ctx) as executor:
            trial_count = 0
            
            while trial_count < config.n_trials and not self._should_stop:
                # Generate parameters for next batch
                batch_size = min(n_jobs, config.n_trials - trial_count)
                futures = []
                
                for _ in range(batch_size):
                    # Create a trial to get suggested parameters
                    trial = self._study.ask()
                    params = {}
                    for param_range in config.parameter_ranges:
                        params[param_range.name] = param_range.suggest(trial)
                    
                    # Submit to process pool
                    future = executor.submit(
                        _run_trial_in_process,
                        objective_func,
                        params,
                        trial.number,
                    )
                    futures.append((future, trial, params))
                    trial_count += 1
                
                # Collect results from this batch
                for future, trial, params in futures:
                    try:
                        # Use timeout if configured
                        result = future.result(timeout=config.timeout)
                        
                        if result.status == "complete" and result.value is not None:
                            self._study.tell(trial, result.value)
                            for key, val in result.metrics.items():
                                trial.set_user_attr(key, val)
                        else:
                            # Trial failed, pruned, or crashed
                            self._study.tell(trial, state=optuna.trial.TrialState.PRUNED)
                        
                        self._results.append(result)
                        
                        if callback:
                            callback(result)
                            
                    except TimeoutError:
                        logger.warning(f"Trial {trial.number} timed out")
                        self._study.tell(trial, state=optuna.trial.TrialState.FAIL)
                        
                        result = OptimizationResult(
                            trial_number=trial.number,
                            params=params,
                            value=None,
                            status="timeout",
                            error_message=f"Trial exceeded timeout of {config.timeout}s",
                        )
                        self._results.append(result)
                        
                        if callback:
                            callback(result)
                            
                    except Exception as e:
                        # Process crashed - this is the crash isolation in action
                        logger.error(f"Trial {trial.number} process crashed: {e}")
                        self._study.tell(trial, state=optuna.trial.TrialState.FAIL)
                        
                        result = OptimizationResult(
                            trial_number=trial.number,
                            params=params,
                            value=None,
                            status="crashed",
                            error_message=f"Process crashed: {str(e)}",
                        )
                        self._results.append(result)
                        
                        if callback:
                            callback(result)
    
    def get_parameter_importance(self) -> Dict[str, float]:
        """
        Get parameter importance scores using Optuna's importance evaluator.
        
        Returns:
            Dictionary of parameter name to importance score (0-1)
        """
        if self._study is None or len(self._study.trials) == 0:
            return {}
        
        try:
            importance = optuna.importance.get_param_importances(self._study)
            return dict(importance)
        except Exception as e:
            logger.warning(f"Failed to compute parameter importance: {e}")
            return {}
    
    def get_optimization_history(self) -> List[OptimizationResult]:
        """
        Get the history of all optimization trials.
        
        Returns:
            List of OptimizationResult for all trials
        """
        return self._results.copy()
    
    def stop(self) -> None:
        """Stop the current optimization run."""
        self._should_stop = True
        logger.info("Optimization stop requested")
    
    def get_study(self) -> Optional[optuna.Study]:
        """
        Get the underlying Optuna study.
        
        Returns:
            Optuna Study object or None
        """
        return self._study
    
    def validate_params_in_bounds(
        self,
        params: Dict[str, Any],
        config: OptimizationConfig,
    ) -> Tuple[bool, List[str]]:
        """
        Validate that all parameters are within their specified bounds.
        
        Args:
            params: Parameter values to validate
            config: Optimization configuration with parameter ranges
        
        Returns:
            Tuple of (is_valid, list_of_violations)
        """
        violations = []
        
        for param_range in config.parameter_ranges:
            if param_range.name not in params:
                violations.append(f"Missing parameter: {param_range.name}")
                continue
            
            value = params[param_range.name]
            if not param_range.validate_value(value):
                if param_range.param_type == ParameterType.CATEGORICAL:
                    violations.append(
                        f"Parameter '{param_range.name}' value {value} "
                        f"not in choices {param_range.choices}"
                    )
                else:
                    violations.append(
                        f"Parameter '{param_range.name}' value {value} "
                        f"out of bounds [{param_range.low}, {param_range.high}]"
                    )
        
        return len(violations) == 0, violations


# Convenience functions for creating parameter ranges

def int_range(
    name: str,
    low: int,
    high: int,
    step: int = 1,
) -> ParameterRange:
    """Create an integer parameter range."""
    return ParameterRange(
        name=name,
        param_type=ParameterType.INT,
        low=low,
        high=high,
        step=step,
    )


def float_range(
    name: str,
    low: float,
    high: float,
    step: Optional[float] = None,
    log: bool = False,
) -> ParameterRange:
    """Create a float parameter range."""
    param_type = ParameterType.LOG_FLOAT if log else ParameterType.FLOAT
    return ParameterRange(
        name=name,
        param_type=param_type,
        low=low,
        high=high,
        step=step,
        log=log,
    )


def categorical(
    name: str,
    choices: List[Any],
) -> ParameterRange:
    """Create a categorical parameter."""
    return ParameterRange(
        name=name,
        param_type=ParameterType.CATEGORICAL,
        choices=choices,
    )


__all__ = [
    "OptimizerError",
    "OptimizationObjective",
    "OptimizationAlgorithm",
    "ParameterType",
    "ParameterRange",
    "OptimizationConfig",
    "OptimizationResult",
    "OptimizationSummary",
    "ObjectiveFunction",
    "IOptimizer",
    "ParameterOptimizer",
    "ProcessIsolatedOptimizer",
    "int_range",
    "float_range",
    "categorical",
]
