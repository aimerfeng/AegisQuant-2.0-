# Changelog

All notable changes to Titan-Quant will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- 整合配置文件：将 setup.cfg 配置迁移至 pyproject.toml，删除冗余的 setup.cfg
- 现代化类型注解：使用 `from __future__ import annotations` 支持 Python 3.10+ 语法
- 增强 .gitignore：添加更多量化开发相关的忽略规则

### Performance Optimizations (2026-01-05)
- [ParquetStorage] 添加 Predicate Pushdown 支持
  - `load_bar_data()` 和 `load_tick_data()` 方法新增可选 `filters` 参数
  - 支持 PyArrow filters 语法实现谓词下推，减少 I/O 开销
  - 对于包含多个 symbol 的大型 Parquet 文件可显著提升性能
  - 改动文件: core/data/storage.py

- [ParquetDataProvider] 更新性能文档
  - 确认已使用 `itertuples()` 替代 `iterrows()` (8-10x 性能提升)
  - 添加 Predicate Pushdown 支持说明
  - 改动文件: core/data/providers/parquet_provider.py

- [MySQLDataProvider] 更新性能文档
  - 确认使用 DictCursor 避免 ORM 开销
  - 确认使用 raw SQL + pd.read_sql 批量读取
  - 绕过 ORM 对象实例化 (Hydration) 开销
  - 改动文件: core/data/providers/mysql_provider.py

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

## [Task 7] 数据源插件模块 - 2026-01-05

### Added
- [Task 7.1] 实现 AbstractDataProvider 接口
  - 创建 core/data/provider.py
  - 实现 ProviderStatus 枚举 (DISCONNECTED, CONNECTING, CONNECTED, ERROR)
  - 实现 HistoryRequest dataclass (历史数据请求参数)
  - 实现 ProviderInfo dataclass (数据源信息)
  - 实现 AbstractDataProvider 抽象基类:
    - connect(), disconnect(), is_connected() 连接管理
    - load_bar_history(), load_tick_history() 数据加载
    - get_available_symbols(), get_dominant_contract() 合约查询
    - download_and_cache() 数据缓存
    - get_provider_name(), get_provider_info() 元信息
    - validate_request() 请求验证
  - 改动文件: core/data/provider.py

- [Task 7.2] 实现 ParquetDataProvider
  - 创建 core/data/providers/parquet_provider.py
  - 实现本地 Parquet 文件数据源
  - 支持 Bar 和 Tick 数据加载
  - 支持按日期范围过滤
  - 支持获取可用交易所、合约、时间间隔列表
  - 支持获取数据时间范围
  - 改动文件: core/data/providers/parquet_provider.py

- [Task 7.3] 实现 MySQLDataProvider
  - 创建 core/data/providers/mysql_provider.py
  - 实现 MySQL 数据源连接和查询
  - 支持 pymysql 可选依赖 (未安装时提示安装)
  - 支持自定义表名 (bar_table, tick_table)
  - 支持 Bar 和 Tick 数据加载
  - 支持主力合约查询 (基于成交量)
  - 支持数据下载并缓存为 Parquet
  - 改动文件: core/data/providers/mysql_provider.py

- [Task 7.4] 实现 MongoDBDataProvider
  - 创建 core/data/providers/mongodb_provider.py
  - 实现 MongoDB 数据源连接和查询
  - 支持 pymongo 可选依赖 (未安装时提示安装)
  - 支持用户名/密码认证
  - 支持自定义集合名 (bar_collection, tick_collection)
  - 支持 Bar 和 Tick 数据加载
  - 支持主力合约查询 (基于聚合管道)
  - 支持创建推荐索引 (create_indexes)
  - 支持 L2 数据 (嵌套文档)
  - 改动文件: core/data/providers/mongodb_provider.py

- [Task 7.5] 实现数据源管理器
  - 创建 core/data/provider_manager.py
  - 实现 ProviderConfig dataclass (数据源配置)
  - 实现 DataProviderManager 类:
    - 内置 parquet, mysql, mongodb 三种数据源类型
    - register_provider_type() 注册自定义数据源类型
    - add_provider(), remove_provider() 管理数据源实例
    - connect(), disconnect(), switch_provider() 连接管理
    - load_bar_history(), load_tick_history() 统一数据加载接口
    - get_available_symbols(), get_dominant_contract() 统一查询接口
    - export_configs(), import_configs() 配置导入导出
  - 实现全局管理器实例 (get_provider_manager, reset_provider_manager)
  - 改动文件: core/data/provider_manager.py

- 更新 core/data/providers/__init__.py 导出所有数据源
  - 导出: ParquetDataProvider, MySQLDataProvider, MongoDBDataProvider
  - 改动文件: core/data/providers/__init__.py

- 更新 core/data/__init__.py 导出数据源相关类型
  - 导出: ProviderStatus, HistoryRequest, ProviderInfo, AbstractDataProvider
  - 导出: ProviderConfig, DataProviderManager, get_provider_manager, reset_provider_manager
  - 导出: ParquetDataProvider, MySQLDataProvider, MongoDBDataProvider
  - 改动文件: core/data/__init__.py

## [Task 9] 快照管理器模块 - 2026-01-05

### Added
- [Task 9.1] 实现快照数据类
  - 创建 core/engine/snapshot.py
  - 实现 AccountState dataclass (账户状态: cash, frozen_margin, available_balance)
  - 实现 PositionState dataclass (持仓状态: symbol, direction, volume, cost_price, unrealized_pnl)
  - 实现 StrategyState dataclass (策略状态: strategy_id, class_name, parameters, variables)
  - 实现 Snapshot dataclass (系统快照: 版本号, 账户, 持仓, 策略, 事件序号, 数据位置)
  - 改动文件: core/engine/snapshot.py

- [Task 9.2] 实现 SnapshotManager 类
  - 实现 ISnapshotManager 抽象接口
  - 实现 SnapshotManager 类:
    - create_snapshot() 创建当前状态快照
    - save_snapshot() 保存快照到磁盘 (JSON 格式)
    - load_snapshot() 从磁盘加载快照
    - restore_snapshot() 恢复快照状态
    - is_compatible() 版本兼容性检查 (主版本号必须匹配)
  - 支持 EventBus 集成 (获取/恢复事件序号)
  - 改动文件: core/engine/snapshot.py

- [Task 9.3] 编写快照属性测试
  - 创建 tests/test_snapshot.py
  - Property 10: Snapshot Round-Trip ✓ PASSED
    - 测试快照保存/加载往返数据一致性
    - 测试账户状态往返
    - 测试持仓状态往返
    - 测试策略状态往返
  - 测试版本兼容性检查
  - 测试快照恢复功能
  - 改动文件: tests/test_snapshot.py

- 更新 core/engine/__init__.py 导出快照相关类型
  - 导出: AccountState, PositionState, StrategyState, Snapshot, ISnapshotManager, SnapshotManager
  - 改动文件: core/engine/__init__.py

## [Task 10] 回放控制器模块 - 2026-01-05

### Added
- [Task 10.1] 实现 ReplayController 类
  - 创建 core/engine/replay.py
  - 实现 ReplayState 枚举 (IDLE, PLAYING, PAUSED, STOPPED)
  - 实现 ReplaySpeed 枚举 (1x, 2x, 4x, 10x, MAX)
  - 实现 ReplayConfig dataclass (回放配置)
  - 实现 ReplayStatus dataclass (回放状态)
  - 实现 IReplayController 抽象接口
  - 实现 ReplayController 类:
    - initialize() 初始化回放数据
    - play(), pause(), resume() 播放控制
    - step() 单步执行
    - stop() 停止回放
    - set_speed() 设置回放速度
    - save_snapshot(), load_snapshot() 快照集成
    - seek_to_index(), seek_to_time() 跳转功能
    - get_status(), get_progress() 状态查询
  - 与 EventBus 和 SnapshotManager 集成
  - 改动文件: core/engine/replay.py

- [Task 10.2] 编写回放控制属性测试
  - 创建 tests/test_replay_controller.py
  - Property 9: Single Step Precision ✓ PASSED
    - 测试单步执行精确前进一个事件
    - 测试多次单步顺序执行
    - 测试单步发布恰好一个事件
    - 测试单步更新当前时间
  - 测试状态转换 (IDLE -> PAUSED -> PLAYING -> STOPPED)
  - 测试速度控制
  - 测试快照集成
  - 测试跳转功能
  - 测试进度计算
  - 改动文件: tests/test_replay_controller.py

- 更新 core/engine/__init__.py 导出回放控制器相关类型
  - 导出: ReplayState, ReplaySpeed, ReplayConfig, ReplayStatus, IReplayController, ReplayController
  - 改动文件: core/engine/__init__.py

- 添加 ENGINE_NOT_INITIALIZED 错误码到 core/exceptions.py
  - 改动文件: core/exceptions.py

## [Task 11] 策略管理器模块 - 2026-01-05

### Added
- [Task 11.1] 实现策略参数解析
  - 创建 core/strategies/manager.py
  - 实现 HotReloadPolicy 枚举 (RESET, PRESERVE, SELECTIVE)
  - 实现 ParameterType 枚举 (INT, FLOAT, STRING, BOOL, ENUM)
  - 实现 UIWidget 枚举 (INPUT, SLIDER, DROPDOWN, CHECKBOX)
  - 实现 StrategyParameter dataclass (策略参数定义)
  - 实现 ReloadResult dataclass (重载结果)
  - 实现 StrategyInfo dataclass (策略信息)
  - 实现 ParameterExtractor 类:
    - 从策略类提取参数定义
    - 自动推断参数类型
    - 自动选择 UI 控件 (有范围用 SLIDER，有选项用 DROPDOWN)
    - 排除基类参数 (strategy_name, symbols)
  - 改动文件: core/strategies/manager.py

- [Task 11.2] 实现热重载功能
  - 实现 IStrategyManager 抽象接口
  - 实现 StrategyManager 类:
    - load_strategy_file() 加载策略文件
    - get_parameters() 获取策略参数
    - set_parameters() 设置策略参数
    - hot_reload() 热重载策略 (支持三种策略)
    - rollback() 回滚到重载前状态
    - get_state_variables() 获取策略状态变量
    - list_strategies() 列出所有策略
  - 实现 @preserve 装饰器用于标记需要保留的变量
  - 改动文件: core/strategies/manager.py

- [Task 11.3] 创建策略模板
  - 创建 core/strategies/template.py
  - 实现 TradeSignal dataclass (交易信号)
  - 实现 CtaTemplate 基类:
    - 生命周期方法: on_init(), on_start(), on_stop()
    - 数据回调: on_tick(), on_bar(), on_order(), on_trade()
    - 交易方法: buy(), sell(), short(), cover()
    - 状态管理: get_state(), set_state()
    - 日志方法: log_info(), log_warning(), log_error()
  - 改动文件: core/strategies/template.py

- [Task 11.4] 编写策略管理属性测试
  - 创建 tests/test_strategy_manager.py
  - Property 14: Strategy Parameter Mapping ✓ PASSED
    - 测试简单参数提取
    - 测试扩展参数提取 (min/max/options)
    - 测试类型推断
    - 测试 UI 控件映射
    - 测试参数序列化往返
  - Property 15: Hot Reload Policy Compliance ✓ PASSED
    - 测试 RESET 策略清除所有变量
    - 测试 PRESERVE 策略保留所有变量
    - 测试 SELECTIVE 策略保留指定变量
    - 测试重载结果包含变量列表
  - 测试策略管理器基础功能
  - 测试 CtaTemplate 模板
  - 改动文件: tests/test_strategy_manager.py

- 更新 core/strategies/__init__.py 导出策略相关类型
  - 导出: HotReloadPolicy, ParameterType, UIWidget, StrategyParameter, ReloadResult, StrategyInfo
  - 导出: ParameterExtractor, IStrategyManager, StrategyManager, preserve
  - 导出: TradeSignal, CtaTemplate
  - 改动文件: core/strategies/__init__.py

## [Task 12] Checkpoint - 核心引擎测试验证 - 2026-01-05

### Verified
- ✅ 所有 107 个测试通过
- ✅ 事件总线模块 (Task 2): Property 1 - Event Sequence Monotonicity
- ✅ 撮合引擎模块 (Task 5): Property 13 - Trade Record Completeness
- ✅ 数据治理模块 (Task 6): Property 3-7 - Data Format/Fill/Outlier/Alignment/Persistence
- ✅ 快照管理器模块 (Task 9): Property 10 - Snapshot Round-Trip
- ✅ 回放控制器模块 (Task 10): Property 9 - Single Step Precision
- ✅ 策略管理器模块 (Task 11): Property 14-15 - Parameter Mapping/Hot Reload Policy
- 测试执行时间: 59.91s


## [Task 13] 审计日志模块 - 2026-01-05

### Added
- [Task 13.1-13.4] 审计日志完整实现
  - 创建 utils/audit.py
  - 实现 ActionType 枚举 (MANUAL_TRADE, AUTO_TRADE, PARAM_CHANGE, etc.)
  - 实现 AuditRecord dataclass (审计记录: SHA-256 哈希, 链式哈希)
  - 实现 IAuditLogger 抽象接口
  - 实现 AuditLogger 类:
    - log_trade() 记录交易
    - log_param_change() 记录参数修改
    - log_action() 记录通用操作
    - verify_integrity() 验证日志完整性
    - get_checksum() 获取日志文件校验和
  - 实现 RotatingFileHandler 线程安全写入
  - 实现链式哈希机制 (每条记录包含前一条记录的哈希)
  - 实现 Checksum 维护
  - 实现启动时完整性检查
  - Property 22: Audit Record Completeness ✓ PASSED
  - Property 23: Audit Chain Hash Integrity ✓ PASSED
  - Property 24: Audit Integrity Verification ✓ PASSED
  - 改动文件: utils/audit.py, tests/test_audit_logger.py

## [Task 14] 加密模块 - 2026-01-05

### Added
- [Task 14.1] 实现 Fernet 加密工具
  - 创建 utils/encrypt.py
  - 实现 EncryptionError 异常类
  - 实现 IEncryptionService 抽象接口
  - 实现 FernetEncryption 类:
    - encrypt() 加密明文数据
    - decrypt() 解密密文数据
    - generate_key() 生成新密钥
    - load_key() 从文件加载密钥
    - save_key() 保存密钥到文件 (限制权限 0o600)
    - rotate_key() 轮换密钥
  - 实现 keyfile.key 密钥文件管理
  - 实现全局加密服务实例 (get_encryption_service)
  - 改动文件: utils/encrypt.py

- [Task 14.2] 实现敏感数据日志过滤
  - 实现 SensitiveDataFilter 类 (logging.Filter):
    - 自动检测并替换 API keys, passwords, secrets, tokens
    - 支持正则表达式模式匹配
    - 支持字典键名匹配
    - 支持自定义模式和敏感键
  - 实现 create_secure_logger() 创建带过滤器的日志器
  - 默认模式覆盖: api_key, secret_key, password, token, Fernet 密文
  - 改动文件: utils/encrypt.py

- [Task 14.3] 实现 exchange_keys 表操作
  - 创建 core/data/key_store.py
  - 实现 Permission 枚举 (READ, TRADE, WITHDRAW)
  - 实现 ExchangeKey dataclass (加密存储的 API 密钥)
  - 实现 DecryptedKey dataclass (解密后的密钥, 安全 repr)
  - 实现 IKeyStore 抽象接口
  - 实现 SQLiteKeyStore 类:
    - store_key() 存储新 API 密钥 (自动加密)
    - get_key() 获取并解密 API 密钥
    - get_keys_by_user() 获取用户所有密钥
    - get_keys_by_exchange() 按交易所获取密钥
    - update_key() 更新密钥
    - delete_key() 删除密钥
    - deactivate_key() 停用密钥
    - has_permission() 检查权限
  - 改动文件: core/data/key_store.py

- [Task 14.4] 编写加密模块属性测试
  - 创建 tests/test_encryption.py
  - Property 20: Sensitive Data Encryption Round-Trip ✓ PASSED
    - 测试加密/解密往返一致性
    - 测试任意文本加密往返
    - 测试 KeyStore 存储/读取往返
    - 测试不同密钥产生不同密文
    - 测试错误密钥解密失败
  - Property 21: Sensitive Data Log Exclusion ✓ PASSED
    - 测试 API key 在日志中被替换为 [REDACTED]
    - 测试 password 在日志中被替换为 [REDACTED]
    - 测试 secret_key 在日志中被替换为 [REDACTED]
    - 测试 DecryptedKey repr 不暴露敏感数据
    - 测试字典参数中敏感键被替换
  - 单元测试: KeyStore CRUD 操作, 权限检查
  - 改动文件: tests/test_encryption.py

- 更新 utils/__init__.py 导出加密相关类型
  - 导出: EncryptionError, IEncryptionService, FernetEncryption
  - 导出: SensitiveDataFilter, create_secure_logger
  - 导出: get_encryption_service, encrypt, decrypt
  - 改动文件: utils/__init__.py

### Verified
- ✅ 所有 137 个测试通过
- ✅ Property 20: Sensitive Data Encryption Round-Trip
- ✅ Property 21: Sensitive Data Log Exclusion
- 测试执行时间: 76.03s

## [Task 15] 风控模块 - 2026-01-05

### Added
- [Task 15.1] 实现 RiskController 类
  - 创建 core/engine/risk.py
  - 实现 RiskTriggerType 枚举 (DAILY_DRAWDOWN, SINGLE_LOSS, POSITION_RATIO, CONSECUTIVE_LOSSES)
  - 实现 RiskLevel 枚举 (NORMAL, WARNING, CIRCUIT_BREAKER)
  - 实现 RiskConfig 数据类:
    - max_daily_drawdown: 最大单日回撤阈值
    - max_single_loss: 最大单笔亏损阈值
    - max_position_ratio: 最大持仓比例阈值
    - enable_auto_liquidation: 是否启用自动平仓
    - warning_*: 预警阈值
    - consecutive_losses_threshold: 连续亏损次数阈值
  - 实现 RiskTriggerEvent 数据类 (触发事件记录)
  - 实现 AccountSnapshot 数据类 (账户状态快照)
  - 实现 TradeResult 数据类 (交易结果)
  - 实现 IRiskController 抽象接口
  - 实现 RiskController 类:
    - check_drawdown(): 检查回撤是否超阈值
    - check_single_loss(): 检查单笔亏损是否超阈值
    - check_position_ratio(): 检查持仓比例是否超阈值
    - update_account(): 更新账户状态并检查风控
    - record_trade(): 记录交易并检查单笔亏损
    - trigger_circuit_breaker(): 触发熔断并强制平仓
    - reset_daily_state(): 重置每日状态
    - set_liquidation_callback(): 设置平仓回调
    - set_alert_callback(): 设置告警回调
  - 改动文件: core/engine/risk.py

- [Task 15.2] 实现风控配置加载
  - RiskConfig.from_yaml() 从 risk_control.yaml 读取配置
  - 支持 risk 节点和 thresholds 节点配置
  - 支持 warning 和 circuit_breaker 分级阈值
  - 改动文件: core/engine/risk.py

- [Task 15.3] 编写风控属性测试
  - 创建 tests/test_risk_controller.py
  - Property 17: Risk Control Trigger ✓ PASSED
    - test_property_17_drawdown_trigger: 测试回撤触发熔断
    - test_property_17_single_loss_trigger: 测试单笔亏损触发熔断
    - test_property_17_full_circuit_breaker: 测试完整熔断流程
  - 单元测试:
    - RiskConfig 默认值、验证、YAML加载、序列化
    - AccountSnapshot 回撤计算、持仓比例计算、零权益处理
    - RiskController 各级别检查、熔断触发、连续亏损、回调机制
  - 改动文件: tests/test_risk_controller.py

- 更新 core/engine/__init__.py 导出风控相关类型
  - 导出: RiskTriggerType, RiskLevel, RiskConfig, RiskTriggerEvent
  - 导出: AccountSnapshot, TradeResult, LiquidationCallback, AlertCallback
  - 导出: IRiskController, RiskController
  - 改动文件: core/engine/__init__.py

### Verified
- ✅ 所有 161 个测试通过
- ✅ Property 17: Risk Control Trigger (3 sub-tests)
- 测试执行时间: 103.23s


## [Task 16] 告警系统模块 - 2026-01-05

### Added
- [Task 16.1] 实现告警数据类和接口
  - 创建 utils/notifier.py
  - 实现 AlertType 枚举 (SYNC, ASYNC)
  - 实现 AlertChannel 枚举 (EMAIL, WEBHOOK, SYSTEM_NOTIFICATION)
  - 实现 AlertSeverity 枚举 (INFO, WARNING, ERROR, CRITICAL)
  - 实现 AlertEventType 枚举 (RISK_TRIGGER, STRATEGY_ERROR, BACKTEST_COMPLETE, etc.)
  - 实现 Alert dataclass (告警消息: alert_id, alert_type, severity, title, message, etc.)
  - 实现 AlertConfig dataclass (告警配置: event_type, alert_type, channels, severity)
  - 实现 EmailConfig dataclass (SMTP 邮件配置)
  - 实现 WebhookConfig dataclass (Webhook 配置)
  - 改动文件: utils/notifier.py

- [Task 16.2] 实现同步/异步告警
  - 实现 IAlertSystem 抽象接口
  - 实现 AlertSystem 类:
    - send_sync_alert(): 发送同步告警 (阻塞直到确认或超时)
    - send_async_alert(): 发送异步告警 (后台线程发送，立即返回)
    - acknowledge_alert(): 确认告警
    - configure_event_alert(): 配置事件告警规则
    - send_event_alert(): 根据配置发送告警
    - get_alert(), get_all_alerts(), get_unacknowledged_alerts(): 查询告警
  - 实现 ThreadPoolExecutor 后台发送
  - 实现 threading.Event 同步等待机制
  - 改动文件: utils/notifier.py

- [Task 16.3] 实现通知渠道
  - 实现 INotificationChannel 抽象接口
  - 实现 EmailChannel 类:
    - SMTP 邮件发送 (支持 TLS/SSL)
    - 纯文本和 HTML 格式邮件
    - 根据严重级别设置颜色
  - 实现 WebhookChannel 类:
    - 支持飞书 (Feishu) 消息格式
    - 支持钉钉 (DingTalk) Markdown 格式
    - 支持 Slack attachments 格式
    - 支持自定义 Webhook 格式
  - 实现 SystemNotificationChannel 类:
    - 本地通知队列
    - 回调函数支持
    - 供 UI 客户端获取待显示通知
  - 改动文件: utils/notifier.py

- [Task 16.4] 编写告警系统属性测试
  - 创建 tests/test_alert_system.py
  - Property 18: Alert Type Classification ✓ PASSED
    - test_alert_type_matches_config: 测试告警类型与配置匹配
    - test_direct_alert_type_preserved: 测试直接发送的告警类型保持不变
    - test_sync_alert_blocks_until_acknowledged: 测试同步告警阻塞直到确认
    - test_async_alert_does_not_block: 测试异步告警不阻塞
  - 单元测试:
    - Alert 序列化/反序列化
    - Alert 确认功能
    - AlertConfig 序列化/反序列化
    - AlertSystem 配置管理
    - 默认配置加载
  - 改动文件: tests/test_alert_system.py

- 更新 utils/__init__.py 导出告警相关类型
  - 导出: AlertType, AlertChannel, AlertSeverity, AlertEventType
  - 导出: Alert, AlertConfig, EmailConfig, WebhookConfig
  - 导出: INotificationChannel, IAlertSystem
  - 导出: EmailChannel, WebhookChannel, SystemNotificationChannel
  - 导出: AlertSystem, get_alert_system, set_alert_system
  - 导出: send_sync_alert, send_async_alert
  - 改动文件: utils/__init__.py

### Verified
- ✅ 所有 171 个测试通过
- ✅ Property 18: Alert Type Classification (4 sub-tests)
- 测试执行时间: 105.09s
