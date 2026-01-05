# Changelog

All notable changes to Titan-Quant will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- 整合配置文件：将 setup.cfg 配置迁移至 pyproject.toml，删除冗余的 setup.cfg
- 现代化类型注解：使用 `from __future__ import annotations` 支持 Python 3.10+ 语法
- 增强 .gitignore：添加更多量化开发相关的忽略规则

### Added
- [Task 1.1] 项目初始化与基础架构
  - 创建项目目录结构 (bin/, config/, core/, database/, logs/, strategies/, ui/, reports/, utils/)
  - 创建 README.md, CHANGELOG.md, requirements.txt, pyproject.toml
  - 创建 .gitignore 文件
  - 改动文件: bin/.gitkeep, config/.gitkeep, core/__init__.py, core/engine/__init__.py, 
    core/engine/adapters/__init__.py, core/data/__init__.py, core/data/providers/__init__.py,
    core/strategies/__init__.py, database/.gitkeep, database/ticks/.gitkeep, database/bars/.gitkeep,
    database/cache/.gitkeep, logs/.gitkeep, reports/.gitkeep, strategies/.gitkeep, ui/.gitkeep,
    utils/__init__.py, README.md, CHANGELOG.md, requirements.txt, pyproject.toml, .gitignore

- [Task 1.2] 配置开发环境
  - 创建 config/system_setting.yaml 系统配置模板
  - 创建 config/risk_control.yaml 风控配置模板
  - 配置 pytest, hypothesis 测试框架 (pyproject.toml, setup.cfg)
  - 创建 tests/conftest.py 测试配置
  - 改动文件: config/system_setting.yaml, config/risk_control.yaml, setup.cfg, 
    tests/__init__.py, tests/conftest.py

- [Task 1.3] 创建基础异常类
  - 实现 TitanQuantError 基类
  - 实现 EngineError (引擎错误)
  - 实现 DataError (数据错误)
  - 实现 StrategyError (策略错误)
  - 实现 SnapshotError (快照错误)
  - 实现 AuditIntegrityError (审计完整性错误)
  - 实现 RiskControlError (风控错误)
  - 实现 ErrorCodes 错误码常量类
  - 改动文件: core/exceptions.py, tests/test_exceptions.py

- [Task 2] 事件总线核心模块
  - [Task 2.1] 实现 Event 和 EventType 数据类
    - 创建 core/engine/event.py
    - 实现 Event dataclass (sequence_number, event_type, timestamp, data, source)
    - 实现 EventType 枚举 (TICK, BAR, ORDER, TRADE, POSITION, ACCOUNT, STRATEGY, RISK, SYSTEM)
    - 支持 to_dict() 和 from_dict() 序列化方法
  - [Task 2.2] 实现 EventBus 类
    - 创建 core/engine/event_bus.py
    - 实现 IEventBus 抽象接口
    - 实现 EventBus 类 (线程安全)
    - 实现 publish(), subscribe(), unsubscribe() 方法
    - 实现单调递增序号生成
    - 实现事件队列和回放功能 (replay_from, get_pending_events)
    - 实现事件历史管理 (get_event_history, clear_history)
  - [Task 2.3] 编写 EventBus 属性测试
    - Property 1: Event Sequence Monotonicity (事件序号单调递增)
    - 测试单线程和多线程并发场景
    - 测试历史清除后序号继续递增
  - 改动文件: core/engine/event.py, core/engine/event_bus.py, core/engine/__init__.py, tests/test_event_bus.py

### Fixed
- [Architecture Audit] EventBus 关键修复
  - 🔴 **时间确定性修复**: `publish()` 方法现在接受可选的 `timestamp` 参数
    - 回测时必须注入模拟时间，确保确定性重放
    - 不提供时 timestamp 时默认使用 wall-clock 时间
  - 🟡 **性能优化**: 事件历史存储从 `list` 切换为 `collections.deque`
    - 旧实现使用 list slicing 是 O(N) 操作
    - 新实现使用 deque(maxlen=N) 在 C 层实现 O(1) 淘汰
  - 🟡 **文档澄清**: 明确 EventBus 内存历史是"热缓冲区"
    - 用于 UI 追赶和短期回放
    - 完整崩溃恢复需要 Snapshot 机制 (Task 9) 或 EventPersister
  - 新增测试: `test_timestamp_injection_for_backtesting`
  - 新增测试: `test_timestamp_defaults_to_now_when_not_provided`
  - 改动文件: core/engine/event_bus.py, tests/test_event_bus.py

### Removed
- N/A

## [Task 4] 引擎适配器模块 - 2026-01-05

### Added
- [Task 4.1] 实现数据类型定义
  - 创建 core/engine/types.py
  - 实现 BarData dataclass (K线数据: symbol, exchange, datetime, interval, OHLCV)
  - 实现 TickData dataclass (Tick数据: L1/L2 订单簿支持)
  - 实现 OrderData dataclass (订单数据: 支持手动/自动单标记)
  - 实现 Direction, Offset, OrderStatus, Interval 枚举
  - 支持 to_dict() 和 from_dict() 序列化方法
  - 改动文件: core/engine/types.py

- [Task 4.2] 实现 IEngineAdapter 接口
  - 创建 core/engine/adapter.py
  - 定义 IEngineAdapter 抽象基类
  - 实现 EngineState, BacktestMode 枚举
  - 实现 EngineConfig, BacktestResult dataclass
  - 定义完整的引擎适配器接口方法:
    - initialize(), load_strategy(), unload_strategy()
    - start_backtest(), pause(), resume(), step(), stop()
    - submit_order(), cancel_order(), get_order()
    - get_positions(), get_account(), get_backtest_result()
    - register_callback(), unregister_callback()
  - 改动文件: core/engine/adapter.py

- [Task 4.3] 实现 VeighNa 适配器
  - 创建 core/engine/adapters/veighna_adapter.py
  - 实现 VeighNaAdapter 类继承 IEngineAdapter
  - 支持 VeighNa 可选依赖 (未安装时以 stub 模式运行)
  - 实现完整的引擎生命周期管理
  - 实现订单管理和回调机制
  - 更新 core/engine/__init__.py 导出新类型
  - 更新 core/engine/adapters/__init__.py 导出 VeighNaAdapter
  - 改动文件: core/engine/adapters/veighna_adapter.py, core/engine/adapters/__init__.py, core/engine/__init__.py
