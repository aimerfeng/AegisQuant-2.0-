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

## [Task 5] 撮合引擎模块 - 2026-01-05

### Added
- [Task 5.1] 实现撮合配置和数据类
  - 创建 core/engine/matching.py
  - 实现 MatchingMode 枚举 (L1, L2)
  - 实现 L2SimulationLevel 枚举 (LEVEL_1, LEVEL_2, LEVEL_3)
  - 实现 SlippageModel 枚举 (FIXED, VOLUME_BASED, VOLATILITY_BASED)
  - 实现 MatchingConfig dataclass (撮合配置)
  - 实现 TradeRecord dataclass (成交记录)
  - 实现 MatchingQualityMetrics dataclass (撮合质量指标)
  - 改动文件: core/engine/matching.py

- [Task 5.2] 实现 L1 撮合逻辑
  - 实现基于对价成交的 L1 撮合 (假设无限流动性)
  - 实现手续费计算 (支持最低手续费)
  - 实现滑点计算 (FIXED, VOLUME_BASED, VOLATILITY_BASED 三种模型)
  - 买单以 ask_price 成交，卖单以 bid_price 成交
  - 改动文件: core/engine/matching.py

- [Task 5.3] 实现 L2 撮合逻辑
  - 实现三个模拟等级的 L2 撮合:
    - Level-1: 队列位置估算 (基于订单到达时间)
    - Level-2: 完整订单簿重建 (基于 L2 数据)
    - Level-3: 市场微观结构模拟 (包含隐藏订单估算)
  - 实现队列位置估算算法
  - 实现模拟局限性说明生成 (get_simulation_limitations)
  - 改动文件: core/engine/matching.py

- [Task 5.4] 编写撮合引擎属性测试
  - Property 13: Trade Record Completeness (成交记录完整性)
  - 测试 L1 模式下成交记录包含所有必需字段
  - 测试 L2 模式下成交记录包含 L2 特定字段
  - 测试各种配置组合下的成交记录完整性
  - 创建 tests/test_matching_engine.py
  - 改动文件: tests/test_matching_engine.py

- 更新 core/engine/__init__.py 导出撮合引擎相关类型
  - 导出: MatchingMode, L2SimulationLevel, SlippageModel, MatchingConfig, TradeRecord, MatchingQualityMetrics, IMatchingEngine, MatchingEngine
  - 改动文件: core/engine/__init__.py

### Architecture Audit (Task 5 审计通过 - 2026-01-05)
- ✅ **确定性合规**: 撮合引擎使用 tick.datetime 生成成交记录，无 datetime.now() 调用
- ✅ **L2 架构设计**: 三层模拟等级设计合理，局限性文档完善
- ⚠️ **性能优化 (v2.0)**: process_tick() 遍历所有订单为 O(N)，已添加 TODO 注释
  - 建议: 使用 sortedcontainers.SortedDict 实现价格优先队列
- 🟡 **浮点精度**: float 用于回测可接受，报告生成建议使用 Decimal
- ✅ **测试覆盖**: Hypothesis 属性测试覆盖 L1/L2 所有路径
- 📝 添加架构审计文档: docs/audit/2026-01-05-task5-matching-engine-audit.md
- 改动文件: core/engine/matching.py (添加 TODO 注释)

## [Task 6] 数据治理中心模块 - 2026-01-05

### Added
- [Task 6.1] 实现数据导入功能
  - 创建 core/data/importer.py
  - 实现 DataFormat 枚举 (CSV, EXCEL, PARQUET)
  - 实现 DataImporter 类
  - 实现 CSV, Excel, Parquet 格式自动识别 (基于扩展名和文件头)
  - 使用 Pandas 进行数据加载 (Polars 在 Windows 环境安装失败)
  - 改动文件: core/data/importer.py

- [Task 6.2] 实现数据清洗功能
  - 创建 core/data/cleaner.py
  - 实现 FillMethod 枚举 (FORWARD_FILL, LINEAR, DROP)
  - 实现 CleaningConfig dataclass (清洗配置)
  - 实现 DataQualityReport dataclass (数据质量报告)
  - 实现 DataCleaner 类:
    - 缺失值检测和填充 (Forward Fill, Linear Interpolation)
    - 异常值检测 (3σ 规则，支持自定义阈值)
    - 时间戳对齐验证 (多合约数据对齐检查)
    - Z-score 计算方法
  - 改动文件: core/data/cleaner.py

- [Task 6.3] 实现 Parquet 存储
  - 创建 core/data/storage.py
  - 实现 DataType 枚举 (TICK, BAR)
  - 实现 BarInterval 枚举 (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
  - 实现 StorageConfig dataclass (存储配置)
  - 实现 ParquetStorage 类:
    - 按交易所/合约/周期分类存储
    - Tick 数据: database/ticks/{exchange}/{symbol}/{date}.parquet
    - Bar 数据: database/bars/{exchange}/{symbol}/{interval}.parquet
    - 实现 Tick 和 Bar 数据的 schema 验证
    - 支持 snappy 压缩
    - 实现数据列表和删除功能
  - 改动文件: core/data/storage.py

- [Task 6.4] 编写数据治理属性测试
  - 创建 tests/test_data_governance.py
  - 实现自定义 Hypothesis 策略:
    - valid_numeric_dataframe: 生成有效数值 DataFrame
    - dataframe_with_missing_values: 生成带缺失值的 DataFrame
    - dataframe_with_outliers: 生成带异常值的 DataFrame
    - bar_dataframe: 生成 Bar 数据 DataFrame
    - tick_dataframe: 生成 Tick 数据 DataFrame
  - Property 3: Data Format Detection ✓ PASSED
    - 测试 CSV 格式检测和解析
    - 测试 Parquet 格式检测和解析
  - Property 4: Missing Value Fill Correctness ✓ PASSED
    - 测试 Forward Fill 移除所有空值
    - 测试 Linear Interpolation 移除所有空值
    - 测试 Forward Fill 使用前一个值
  - Property 5: Outlier Detection Accuracy ✓ PASSED
    - 测试检测到的异常值 |z-score| > threshold
    - 测试非异常值 |z-score| <= threshold
    - 测试自定义阈值生效
  - Property 6: Timestamp Alignment Validation ✓ PASSED
    - 测试检测缺失时间戳
    - 测试对齐数据无问题
  - Property 7: Data Persistence Round-Trip ✓ PASSED
    - 测试 Bar 数据保存/加载往返
    - 测试 Tick 数据保存/加载往返
    - 测试存储路径组织正确
  - 单元测试: DataImporter, DataCleaner, ParquetStorage 基础功能
  - 改动文件: tests/test_data_governance.py

- 更新 core/data/__init__.py 导出数据治理相关类型
  - 导出: DataFormat, DataImporter, FillMethod, CleaningConfig, DataQualityReport, DataCleaner, DataType, BarInterval, StorageConfig, ParquetStorage
  - 改动文件: core/data/__init__.py

### Architecture Audit (Task 6 审计通过 - 2026-01-05)
- ✅ **存储策略**: Parquet + Hive 分区设计优秀，最小化回测 I/O 开销
- ✅ **数据完整性**: Forward Fill 符合金融行业标准，时间戳对齐逻辑正确
- ✅ **导入抽象**: 统一接口屏蔽 CSV/Excel/Parquet 格式差异
- ✅ **测试覆盖**: 属性测试验证幂等性、无数据丢失、Schema 一致性
- 🟡 **可扩展性 (v2.0)**: Pandas 适用于 < 10GB 数据，大规模数据考虑 Polars/Dask
- 📝 添加架构审计文档: docs/audit/2026-01-05-task6-data-governance-audit.md

### Fixed (架构审计修复 - 2026-01-05)
- [Task 4 Audit] VeighNaAdapter 架构优化
  - 🔧 **软依赖管理**: 使用 try-except 延迟导入 vnpy，支持无 vnpy 环境运行
    - 添加 TYPE_CHECKING 块支持静态类型检查
    - 定义占位符类型防止 NameError
  - 🔧 **异常边界封装**: 所有 VeighNa 异常被捕获并包装为 Titan-Quant 统一异常
    - `initialize()` -> `EngineError`
    - `load_strategy()` -> `StrategyError`
    - `start_backtest()` -> `EngineError`
    - `submit_order()` -> `EngineError`
    - `cancel_order()` -> `EngineError`
  - 📝 添加架构审计文档: docs/audit/2026-01-05-task4-adapter-audit.md
  - 改动文件: core/engine/adapters/veighna_adapter.py
