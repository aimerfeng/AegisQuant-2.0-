 # Implementation Plan: Titan-Quant

## Overview

本实现计划将 Titan-Quant 量化回测系统分解为可增量执行的任务。每个任务完成后需提交代码到 GitHub 仓库并编写更新日志。

**Git 仓库**: https://github.com/aimerfeng/AegisQuant-2.0-.git

**提交规范**:
- 每个任务完成后执行 `git add . && git commit -m "[Task X.X] 功能描述"` 并 `git push`
- 更新日志记录在 `CHANGELOG.md`，包含：更新内容、设计的功能、改动文件列表

## Tasks

- [x] 1. 项目初始化与基础架构
  - [x] 1.1 创建项目目录结构
    - 按照设计文档创建 bin/, config/, core/, database/, logs/, strategies/, ui/, reports/, utils/ 目录
    - 创建 README.md, CHANGELOG.md, requirements.txt, pyproject.toml
    - 初始化 Git 仓库并关联远程仓库
    - _Requirements: 系统目录结构_

  - [x] 1.2 配置开发环境
    - 创建 Python 虚拟环境配置
    - 配置 pytest, hypothesis 测试框架
    - 创建 config/system_setting.yaml 和 config/risk_control.yaml 模板
    - _Requirements: 10.3_

  - [x] 1.3 创建基础异常类
    - 实现 TitanQuantError 及其子类 (EngineError, DataError, StrategyError, SnapshotError, AuditIntegrityError, RiskControlError)
    - _Requirements: 1.8_

- [ ] 2. 事件总线核心模块
  - [ ] 2.1 实现 Event 和 EventType 数据类
    - 创建 core/engine/event.py
    - 实现 Event dataclass 包含 sequence_number, event_type, timestamp, data, source
    - 实现 EventType 枚举
    - _Requirements: 1.5, 1.6_

  - [ ] 2.2 实现 EventBus 类
    - 实现 IEventBus 接口
    - 实现 publish(), subscribe(), unsubscribe() 方法
    - 实现单调递增序号生成
    - 实现事件队列和回放功能
    - _Requirements: 1.6, 1.7_

  - [ ] 2.3 编写 EventBus 属性测试
    - **Property 1: Event Sequence Monotonicity**
    - **Validates: Requirements 1.7**

- [ ] 3. Checkpoint - 事件总线测试验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 4. 引擎适配器模块
  - [ ] 4.1 实现数据类型定义
    - 创建 core/engine/types.py
    - 实现 BarData, TickData, OrderData dataclass
    - _Requirements: 7.1, 7.2_

  - [ ] 4.2 实现 IEngineAdapter 接口
    - 创建 core/engine/adapter.py
    - 定义抽象基类 IEngineAdapter
    - _Requirements: 1.2_

  - [ ] 4.3 实现 VeighNa 适配器
    - 创建 core/engine/adapters/veighna_adapter.py
    - 实现 VeighNaAdapter 类继承 IEngineAdapter
    - _Requirements: 1.2_

- [ ] 5. 撮合引擎模块
  - [ ] 5.1 实现撮合配置和数据类
    - 创建 core/engine/matching.py
    - 实现 MatchingMode, L2SimulationLevel 枚举
    - 实现 MatchingConfig, TradeRecord, MatchingQualityMetrics dataclass
    - _Requirements: 7.1, 7.2_

  - [ ] 5.2 实现 L1 撮合逻辑
    - 实现基于对价成交的 L1 撮合
    - 实现手续费和滑点计算
    - _Requirements: 7.1, 7.4_

  - [ ] 5.3 实现 L2 撮合逻辑
    - 实现三个模拟等级的 L2 撮合
    - 实现队列位置估算
    - 实现模拟局限性说明生成
    - _Requirements: 7.2, 7.3_

  - [ ] 5.4 编写撮合引擎属性测试
    - **Property 13: Trade Record Completeness**
    - **Validates: Requirements 7.5**

- [ ] 6. 数据治理中心模块
  - [ ] 6.1 实现数据导入功能
    - 创建 core/data/importer.py
    - 实现 CSV, Excel, Parquet 格式识别和解析
    - 使用 Polars 进行高性能数据加载
    - _Requirements: 2.1_

  - [ ] 6.2 实现数据清洗功能
    - 实现缺失值检测和填充 (Forward Fill, Linear)
    - 实现异常值检测 (3σ 规则)
    - 实现时间戳对齐验证
    - _Requirements: 2.2, 2.3, 2.4_

  - [ ] 6.3 实现 Parquet 存储
    - 实现按交易所/合约/周期分类存储
    - 实现 Tick 和 Bar 数据的 Parquet schema
    - _Requirements: 2.6_

  - [ ] 6.4 编写数据治理属性测试
    - **Property 3: Data Format Detection**
    - **Property 4: Missing Value Fill Correctness**
    - **Property 5: Outlier Detection Accuracy**
    - **Property 6: Timestamp Alignment Validation**
    - **Property 7: Data Persistence Round-Trip**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6**

- [ ] 7. 数据源插件模块
  - [ ] 7.1 实现 AbstractDataProvider 接口
    - 创建 core/data/provider.py
    - 定义数据源抽象基类
    - 实现 HistoryRequest 数据类
    - _Requirements: 数据源扩展_

  - [ ] 7.2 实现 ParquetDataProvider
    - 创建 core/data/providers/parquet_provider.py
    - 实现本地 Parquet 文件数据源
    - _Requirements: 数据源扩展_

  - [ ] 7.3 实现 MySQLDataProvider
    - 创建 core/data/providers/mysql_provider.py
    - 实现 MySQL 数据源连接和查询
    - _Requirements: 数据源扩展_

  - [ ] 7.4 实现 MongoDBDataProvider
    - 创建 core/data/providers/mongodb_provider.py
    - 实现 MongoDB 数据源连接和查询
    - _Requirements: 数据源扩展_

  - [ ] 7.5 实现数据源管理器
    - 创建 core/data/provider_manager.py
    - 实现数据源注册、切换、配置管理
    - _Requirements: 数据源扩展_

- [ ] 8. Checkpoint - 数据模块测试验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 9. 快照管理器模块
  - [ ] 9.1 实现快照数据类
    - 创建 core/engine/snapshot.py
    - 实现 AccountState, PositionState, StrategyState, Snapshot dataclass
    - _Requirements: 5.5_

  - [ ] 9.2 实现 SnapshotManager 类
    - 实现 create_snapshot(), save_snapshot(), load_snapshot(), restore_snapshot()
    - 实现版本兼容性检查
    - 使用 JSON 序列化
    - _Requirements: 5.5, 5.6, 5.7_

  - [ ] 9.3 编写快照属性测试
    - **Property 10: Snapshot Round-Trip**
    - **Validates: Requirements 5.5, 5.6**

- [ ] 10. 回放控制器模块
  - [ ] 10.1 实现 ReplayController 类
    - 创建 core/engine/replay.py
    - 实现 pause(), resume(), step(), set_speed() 方法
    - 实现与 EventBus 和 SnapshotManager 的集成
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ] 10.2 编写回放控制属性测试
    - **Property 9: Single Step Precision**
    - **Validates: Requirements 5.3**

- [ ] 11. 策略管理器模块
  - [ ] 11.1 实现策略参数解析
    - 创建 core/strategies/manager.py
    - 实现 StrategyParameter dataclass
    - 实现从策略类提取参数定义
    - _Requirements: 8.2_

  - [ ] 11.2 实现热重载功能
    - 实现 HotReloadPolicy 枚举
    - 实现 hot_reload() 方法支持三种策略
    - 实现 rollback() 回滚功能
    - _Requirements: 8.3, 8.4, 8.5_

  - [ ] 11.3 创建策略模板
    - 创建 core/strategies/template.py
    - 实现 CtaTemplate 基类
    - 实现 @preserve 装饰器
    - _Requirements: 8.6_

  - [ ] 11.4 编写策略管理属性测试
    - **Property 14: Strategy Parameter Mapping**
    - **Property 15: Hot Reload Policy Compliance**
    - **Validates: Requirements 8.2, 8.3**

- [ ] 12. Checkpoint - 核心引擎测试验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 13. 审计日志模块
  - [ ] 13.1 实现审计记录数据类
    - 创建 utils/audit.py
    - 实现 AuditRecord dataclass
    - 实现 SHA-256 哈希计算
    - _Requirements: 14.6_

  - [ ] 13.2 实现 AuditLogger 类
    - 实现 log_trade(), log_param_change(), log_action() 方法
    - 实现链式哈希机制
    - 实现 RotatingFileHandler 线程安全写入
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ] 13.3 实现完整性验证
    - 实现 verify_integrity() 方法
    - 实现 Checksum 维护
    - 实现启动时完整性检查
    - _Requirements: 14.7, 14.8_

  - [ ] 13.4 编写审计日志属性测试
    - **Property 22: Audit Record Completeness**
    - **Property 23: Audit Chain Hash Integrity**
    - **Property 24: Audit Integrity Verification**
    - **Validates: Requirements 14.2, 14.3, 14.6, 14.8**

- [ ] 14. 加密模块
  - [ ] 14.1 实现 Fernet 加密工具
    - 创建 utils/encrypt.py
    - 实现 encrypt(), decrypt() 方法
    - 实现 keyfile.key 管理
    - _Requirements: 13.1, 13.2_

  - [ ] 14.2 实现敏感数据日志过滤
    - 实现自定义 logging Filter
    - 确保敏感数据不输出到日志
    - _Requirements: 13.3_

  - [ ] 14.3 实现 exchange_keys 表操作
    - 创建 core/data/key_store.py
    - 实现 API Key 的加密存储和读取
    - 实现权限管理
    - _Requirements: 13.1, 13.2_

  - [ ] 14.4 编写加密模块属性测试
    - **Property 20: Sensitive Data Encryption Round-Trip**
    - **Property 21: Sensitive Data Log Exclusion**
    - **Validates: Requirements 13.1, 13.3**

- [ ] 15. 风控模块
  - [ ] 15.1 实现 RiskController 类
    - 创建 core/engine/risk.py
    - 实现回撤计算和阈值检查
    - 实现单笔亏损检查
    - 实现熔断触发和强制平仓
    - _Requirements: 10.1, 10.2, 10.4_

  - [ ] 15.2 实现风控配置加载
    - 从 risk_control.yaml 读取配置
    - _Requirements: 10.3_

  - [ ] 15.3 编写风控属性测试
    - **Property 17: Risk Control Trigger**
    - **Validates: Requirements 10.1, 10.2**

- [ ] 16. 告警系统模块
  - [ ] 16.1 实现告警数据类和接口
    - 创建 utils/notifier.py
    - 实现 AlertType, AlertChannel, AlertSeverity 枚举
    - 实现 Alert, AlertConfig dataclass
    - _Requirements: 11.3_

  - [ ] 16.2 实现同步/异步告警
    - 实现 send_sync_alert() 阻塞告警
    - 实现 send_async_alert() 非阻塞告警
    - _Requirements: 11.3, 11.4, 11.5_

  - [ ] 16.3 实现通知渠道
    - 实现 SMTP 邮件发送
    - 实现 Webhook (飞书/钉钉) 发送
    - _Requirements: 11.1, 11.2_

  - [ ] 16.4 编写告警系统属性测试
    - **Property 18: Alert Type Classification**
    - **Validates: Requirements 11.3**

- [ ] 17. Checkpoint - 安全与风控测试验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 18. 用户认证模块
  - [ ] 18.1 实现用户管理
    - 创建 core/auth.py
    - 实现用户创建、密码哈希 (Argon2)
    - 实现 Admin/Trader 角色
    - _Requirements: 12.2_

  - [ ] 18.2 实现登录认证
    - 实现密码验证
    - 实现 KeyStore 解密
    - _Requirements: 12.3_

  - [ ] 18.3 实现权限控制
    - 实现基于角色的访问控制
    - _Requirements: 12.4_

  - [ ] 18.4 编写认证属性测试
    - **Property 19: Role-Based Access Control**
    - **Validates: Requirements 12.4**

- [ ] 19. 参数优化器模块
  - [ ] 19.1 实现 Optuna 集成
    - 创建 core/optimizer.py
    - 实现参数范围配置
    - 实现优化目标 (Sharpe Ratio, Total Return)
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ] 19.2 实现多进程并行优化
    - 实现进程隔离
    - 实现崩溃隔离
    - _Requirements: 9.5, 9.6_

  - [ ] 19.3 编写优化器属性测试
    - **Property 16: Optimizer Parameter Bounds**
    - **Validates: Requirements 9.2**

- [ ] 20. 回测报告生成模块
  - [ ] 20.1 实现报告数据计算
    - 创建 core/report.py
    - 实现 Sharpe Ratio, Max Drawdown, Win Rate 等指标计算
    - _Requirements: 15.2_

  - [ ] 20.2 实现 HTML 报告生成
    - 实现交互式 HTML 模板
    - 实现资金曲线图生成
    - 实现 trades.csv 导出
    - _Requirements: 15.1, 15.3, 15.4_

  - [ ] 20.3 编写报告属性测试
    - **Property 25: Report Metrics Completeness**
    - **Validates: Requirements 15.2**

- [ ] 21. 国际化模块
  - [ ] 21.1 实现 I18nManager 类
    - 创建 utils/i18n.py
    - 实现语言包加载和切换
    - 实现 translate() 方法支持参数插值
    - _Requirements: I18N 支持_

  - [ ] 21.2 创建语言包文件
    - 创建 config/i18n/en.json
    - 创建 config/i18n/zh_cn.json
    - 创建 config/i18n/zh_tw.json
    - 包含错误信息、审计日志类型、告警消息的翻译
    - _Requirements: I18N 支持_

  - [ ] 21.3 集成 I18N 到各模块
    - 审计日志使用 I18N keys
    - 错误消息使用 I18N keys
    - 告警消息使用 I18N keys
    - _Requirements: I18N 支持_

- [ ] 22. Checkpoint - 后端核心功能测试验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 23. 数据库层
  - [ ] 23.1 实现 SQLite Schema
    - 创建 database/schema.sql
    - 实现 users, exchange_keys, strategies, backtest_records, backtest_results, snapshots, alert_configs, data_providers 表
    - _Requirements: 数据模型_

  - [ ] 23.2 实现数据访问层
    - 创建 core/data/repository.py
    - 实现 CRUD 操作
    - _Requirements: 数据模型_

- [ ] 24. WebSocket 通信层
  - [ ] 24.1 实现 WebSocket 服务端
    - 创建 core/server.py
    - 实现消息路由
    - 实现心跳检测
    - _Requirements: 1.1, 1.3, 1.4_

  - [ ] 24.2 实现消息处理器
    - 实现各类消息的处理逻辑
    - 实现状态同步
    - _Requirements: 1.3, 1.4_

- [ ] 25. 手动交易功能
  - [ ] 25.1 实现手动下单接口
    - 实现 MANUAL_ORDER 消息处理
    - 实现订单标记为人工干预单
    - _Requirements: 6.1, 6.2_

  - [ ] 25.2 实现一键清仓
    - 实现 CLOSE_ALL 消息处理
    - _Requirements: 6.4_

  - [ ] 25.3 编写手动交易属性测试
    - **Property 11: Manual Order Marking**
    - **Property 12: Close All Positions**
    - **Validates: Requirements 6.2, 6.3, 6.4**

- [ ] 26. Checkpoint - 后端完整功能测试验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 27. 回测确定性验证
  - [ ] 27.1 编写回测确定性属性测试
    - **Property 2: Backtest Determinism**
    - **Validates: Requirements 1.6, 9.7**

- [ ] 28. 前端项目初始化
  - [ ] 28.1 创建 Electron + React 项目
    - 初始化 ui/ 目录
    - 配置 TypeScript, Webpack
    - 安装依赖 (React, Zustand, Golden-Layout, Monaco Editor, Lightweight-charts)
    - _Requirements: UI 技术栈_

  - [ ] 28.2 实现 WebSocket 客户端服务
    - 创建 ui/src/services/websocket.ts
    - 实现连接、重连、消息收发
    - _Requirements: 1.1, 1.4_

  - [ ] 28.3 实现前端 I18N
    - 集成 react-i18next
    - 加载后端语言包
    - _Requirements: I18N 支持_

- [ ] 29. 前端布局系统
  - [ ] 29.1 实现 Golden-Layout 集成
    - 创建 ui/src/layouts/WorkspaceLayout.tsx
    - 实现多窗口拖拽、吸附、分屏
    - _Requirements: 4.1, 4.2_

  - [ ] 29.2 实现布局持久化
    - 实现布局保存和加载
    - _Requirements: 4.3, 4.4_

  - [ ] 29.3 编写布局持久化属性测试
    - **Property 8: Layout Persistence Round-Trip**
    - **Validates: Requirements 4.3, 4.4**

- [ ] 30. K 线图组件
  - [ ] 30.1 实现 Lightweight-charts 集成
    - 创建 ui/src/components/KLineChart/index.tsx
    - 实现 K 线渲染
    - 实现缩放、拖拽、平移
    - _Requirements: 3.1_

  - [ ] 30.2 实现划线工具
    - 实现趋势线、斐波那契、矩形框
    - 实现坐标暴露给策略
    - _Requirements: 3.2_

  - [ ] 30.3 实现指标面板
    - 实现 MA, MACD, RSI, Bollinger Bands
    - 实现拖拽添加
    - _Requirements: 3.3_

  - [ ] 30.4 实现交易标记
    - 实现开平仓箭头标记
    - 实现悬停显示盈亏详情
    - _Requirements: 3.4, 3.5_

- [ ] 31. 深度图组件
  - [ ] 31.1 实现 OrderBook 组件
    - 创建 ui/src/components/OrderBook/index.tsx
    - 实现买卖十档显示
    - 实现动态更新
    - _Requirements: 3.6_

- [ ] 32. 控制面板组件
  - [ ] 32.1 实现播放控制条
    - 创建 ui/src/components/ControlPanel/PlaybackBar.tsx
    - 实现暂停、播放、加速、单步按钮
    - _Requirements: 5.1_

  - [ ] 32.2 实现手动交易按钮
    - 创建 ui/src/components/ControlPanel/ManualTrade.tsx
    - 实现市价买入/卖出、一键清仓按钮
    - _Requirements: 6.1_

- [ ] 33. 策略 IDE 组件
  - [ ] 33.1 实现 Monaco Editor 集成
    - 创建 ui/src/components/StrategyLab/CodeEditor.tsx
    - 实现 Python 语法高亮、自动补全
    - _Requirements: 8.1_

  - [ ] 33.2 实现参数面板
    - 创建 ui/src/components/StrategyLab/ParamPanel.tsx
    - 实现动态表单生成 (滑块、下拉)
    - _Requirements: 8.2_

  - [ ] 33.3 实现热重载 UI
    - 实现 Reload 按钮
    - 实现重载策略选择
    - _Requirements: 8.3_

- [ ] 34. 数据中心组件
  - [ ] 34.1 实现文件拖拽区
    - 创建 ui/src/components/DataCenter/FileDropzone.tsx
    - 实现文件格式识别
    - _Requirements: 2.1_

  - [ ] 34.2 实现清洗预览
    - 创建 ui/src/components/DataCenter/CleaningPreview.tsx
    - 实现缺失值高亮
    - 实现异常值标记
    - _Requirements: 2.2, 2.3_

  - [ ] 34.3 实现数据源配置
    - 创建 ui/src/components/DataCenter/ProviderConfig.tsx
    - 实现数据源选择和配置
    - _Requirements: 数据源扩展_

- [ ] 35. 登录界面
  - [ ] 35.1 实现登录组件
    - 创建 ui/src/components/Login/index.tsx
    - 实现密码输入和验证
    - _Requirements: 12.1, 12.3_

- [ ] 36. 告警弹窗
  - [ ] 36.1 实现系统通知
    - 实现 Electron 原生通知
    - 实现同步告警弹窗
    - _Requirements: 11.4_

- [ ] 37. 报告查看组件
  - [ ] 37.1 实现报告展示
    - 创建 ui/src/components/Reports/index.tsx
    - 实现指标卡片
    - 实现资金曲线图
    - _Requirements: 15.1, 15.2_

- [ ] 38. Checkpoint - 前端组件测试验证
  - 确保所有测试通过，如有问题请询问用户

- [ ] 39. 状态管理
  - [ ] 39.1 实现 Zustand Store
    - 创建 backtestStore, strategyStore, alertStore, i18nStore
    - 实现状态同步
    - _Requirements: UI 状态管理_

- [ ] 40. 前后端集成
  - [ ] 40.1 实现完整通信流程
    - 连接 WebSocket
    - 实现消息收发
    - 实现状态同步
    - _Requirements: 1.1, 1.3, 1.4_

- [ ] 41. 启动脚本
  - [ ] 41.1 创建启动脚本
    - 创建 bin/start_server.bat (Windows)
    - 创建 bin/start_server.sh (Linux/Mac)
    - 创建 Electron 打包配置
    - _Requirements: 启动脚本_

- [ ] 42. Final Checkpoint - 完整系统测试验证
  - 确保所有测试通过
  - 执行端到端测试
  - 如有问题请询问用户

## Notes

- 所有任务均为必做任务，包括属性测试
- 每个任务完成后需提交代码到 GitHub 并更新 CHANGELOG.md
- Checkpoint 任务用于验证阶段性成果
- 属性测试使用 hypothesis 库实现
- 前端测试使用 Jest + React Testing Library
- 性能优化：使用 Polars 替代 Pandas，核心计算使用 TA-Lib (C底层)
