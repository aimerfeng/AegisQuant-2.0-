# Requirements Document

## Introduction

Titan-Quant 是一个工程级量化交易回测系统，采用守护进程+GUI客户端分离架构，提供极致性能的事件驱动回测引擎和类 TradingView 的交互体验。系统通过适配器模式集成 VeighNa、TA-Lib、Optuna 等高星开源项目，支持 L1/L2 撮合、策略热加载、参数优化和完整的风控审计功能。

## Glossary

- **Titan_Quant_System**: 整体量化回测系统
- **Core_Engine**: 后端回测引擎，通过 Engine_Adapter 接口与底层框架解耦
- **Engine_Adapter**: 引擎适配器接口，支持 VeighNa、自研引擎等多种实现
- **Event_Bus**: 事件驱动架构的核心消息总线，保证事件顺序确定性
- **Matching_Engine**: 撮合引擎，支持 L1/L2 撮合模式，L2 模式需声明模拟等级
- **L2_Simulation_Level**: L2 撮合模拟等级（Level-1: 队列位置估算, Level-2: 完整订单簿重建, Level-3: 市场微观结构模拟）
- **Data_Governance_Hub**: 数据治理中心，负责 ETL 清洗与导入
- **Replay_Controller**: 历史回放控制器，支持暂停、加速、单步调试
- **Strategy_Lab**: 策略管理与开发 IDE
- **Hot_Reload_Policy**: 策略热重载策略（RESET: 重置所有变量, PRESERVE: 保留状态变量, SELECTIVE: 用户指定）
- **Risk_Controller**: 风控模块，负责熔断和通知
- **Audit_Logger**: 审计日志系统，支持不可逆 Hash 校验
- **UI_Client**: Electron + React 前端客户端
- **KLine_Chart**: 基于 Lightweight-charts 的交互式 K 线图组件
- **Optimizer**: 基于 Optuna 的参数优化器
- **Parquet_Store**: Parquet 格式的历史数据存储
- **Snapshot**: 系统状态快照，包含资金、持仓、策略变量、事件队列位置
- **Backtest_Mode**: 回测模式，单线程顺序执行，保证确定性
- **Optimization_Mode**: 优化模式，多进程并行执行，每个进程独立隔离
- **Sync_Alert**: 同步告警，阻塞当前流程直到确认
- **Async_Alert**: 异步告警，不阻塞流程，后台发送

## Requirements

### Requirement 1: 系统架构与稳定性

**User Story:** As a 量化交易员, I want 前后端分离的守护进程架构, so that 前端崩溃不影响后台回测逻辑。

#### Acceptance Criteria

1. THE Core_Engine SHALL 作为独立守护进程运行，与 UI_Client 通过 WebSocket/ZMQ 通信
2. THE Core_Engine SHALL 通过 Engine_Adapter 接口与底层框架解耦，支持 VeighNa、自研引擎等多种实现
3. WHEN UI_Client 崩溃或断开连接, THEN THE Core_Engine SHALL 继续执行当前回测任务并保持状态
4. WHEN UI_Client 重新连接, THEN THE Core_Engine SHALL 恢复状态同步并继续提供数据流
5. THE Event_Bus SHALL 采用事件驱动架构处理所有系统消息
6. THE Event_Bus SHALL 保证事件处理的顺序确定性：相同输入数据和参数必须产生相同的事件序列和结果
7. THE Event_Bus SHALL 使用单调递增的事件序号标识每个事件，支持事件回溯和重放
8. IF Core_Engine 发生未捕获异常, THEN THE Titan_Quant_System SHALL 记录完整堆栈到 sys_error.log 并尝试优雅降级

### Requirement 2: 数据治理与导入

**User Story:** As a 量化研究员, I want 多格式数据导入和自动清洗功能, so that 我可以快速准备高质量的回测数据。

#### Acceptance Criteria

1. WHEN 用户拖拽 CSV、Excel、Parquet 文件到数据中心, THEN THE Data_Governance_Hub SHALL 自动识别格式并解析数据
2. WHEN 数据存在缺失值, THEN THE Data_Governance_Hub SHALL 提供 Forward Fill 和 Linear 插值选项供用户选择
3. WHEN 数据存在偏离 3σ 的异常值, THEN THE Data_Governance_Hub SHALL 自动标记并高亮显示，等待用户确认处理方式
4. WHEN 多合约回测时, THEN THE Data_Governance_Hub SHALL 验证时间戳严格对齐，并报告不对齐的数据点
5. THE Data_Governance_Hub SHALL 支持 Tick 级 L1/L2 数据的导入和内存映射
6. WHEN 数据清洗完成, THEN THE Data_Governance_Hub SHALL 将数据存储为 Parquet 格式，按日期/合约分类

### Requirement 3: 交互式 K 线图可视化

**User Story:** As a 交易员, I want 类 TradingView 的专业 K 线图, so that 我可以进行技术分析和回测结果可视化。

#### Acceptance Criteria

1. THE KLine_Chart SHALL 基于 WebGL 渲染，支持流畅的缩放、拖拽和平移操作
2. WHEN 用户在 K 线图上划线, THEN THE KLine_Chart SHALL 支持趋势线、斐波那契回调线、矩形框，并将坐标暴露给策略读取
3. THE KLine_Chart SHALL 支持拖拽添加 MA、MACD、RSI、Bollinger Bands 等主副图指标
4. WHEN 回测产生交易信号, THEN THE KLine_Chart SHALL 在对应 K 线上用箭头标记开平仓点位
5. WHEN 用户悬停在交易标记上, THEN THE KLine_Chart SHALL 显示该笔交易的盈亏详情
6. THE UI_Client SHALL 提供独立的 OrderBook 深度图窗口，动态展示买一到买十的变化

### Requirement 4: 多窗口布局管理

**User Story:** As a 用户, I want 类 IDE 的多窗口拖拽布局, so that 我可以自定义工作区并保存预设。

#### Acceptance Criteria

1. THE UI_Client SHALL 基于 Golden-Layout 实现多窗口拖拽、吸附、分屏功能
2. WHEN 用户调整窗口布局, THEN THE UI_Client SHALL 支持将 K 线图、日志、深度图等组件自由排列
3. WHEN 用户保存布局, THEN THE UI_Client SHALL 将当前布局存储为"工作区预设"
4. WHEN 用户加载预设, THEN THE UI_Client SHALL 恢复之前保存的窗口布局

### Requirement 5: 回测回放控制

**User Story:** As a 策略开发者, I want 录像机式的回放控制, so that 我可以逐帧分析策略行为。

#### Acceptance Criteria

1. THE Replay_Controller SHALL 在界面底部提供播放条，支持暂停、播放、2x/4x/10x 加速、单步调试
2. WHEN 用户点击暂停, THEN THE Replay_Controller SHALL 立即冻结回测状态
3. WHEN 用户点击单步调试, THEN THE Replay_Controller SHALL 前进一个时间单位并更新所有视图
4. WHEN 用户调整播放速度, THEN THE Replay_Controller SHALL 按指定倍速推进回测时间
5. WHEN 用户点击"保存快照", THEN THE Replay_Controller SHALL 将以下内容序列化到磁盘：
   - 账户资金状态（现金、已用保证金、可用余额）
   - 所有持仓信息（合约、数量、成本价、浮动盈亏）
   - 策略实例的所有状态变量
   - Event_Bus 当前事件序号和待处理事件队列
   - 数据流当前位置（时间戳、数据索引）
6. WHEN 用户加载快照, THEN THE Replay_Controller SHALL 完整恢复上述所有状态，从该时间点继续执行
7. THE Snapshot SHALL 包含版本号，WHEN 快照版本与当前系统版本不兼容, THEN THE Replay_Controller SHALL 拒绝加载并提示用户

### Requirement 6: 手动交易干预

**User Story:** As a 交易员, I want 在回放过程中手动下单, so that 我可以测试人工干预对策略的影响。

#### Acceptance Criteria

1. WHILE 回放模式运行中, THE UI_Client SHALL 提供"市价买入/卖出"按钮供用户手动下单
2. WHEN 用户手动下单, THEN THE Matching_Engine SHALL 执行订单并标记为"人工干预单"
3. THE Audit_Logger SHALL 区分记录策略自动单和人工干预单
4. WHEN 用户点击"一键清仓", THEN THE Matching_Engine SHALL 立即平掉所有持仓

### Requirement 7: 撮合引擎

**User Story:** As a 量化研究员, I want 支持 L1/L2 撮合模式, so that 我可以模拟不同精度的成交场景。

#### Acceptance Criteria

1. THE Matching_Engine SHALL 支持 L1 撮合模式（基于对价成交，假设无限流动性）
2. THE Matching_Engine SHALL 支持 L2 撮合模式，并明确声明模拟等级：
   - Level-1: 队列位置估算（基于订单到达时间和价格优先级）
   - Level-2: 完整订单簿重建（基于历史 L2 快照数据）
   - Level-3: 市场微观结构模拟（包含隐藏订单、冰山订单估算）
3. WHEN 用户选择 L2 撮合, THEN THE Matching_Engine SHALL 在报告中明确标注所使用的模拟等级及其局限性
4. WHEN 用户配置回测参数, THEN THE Matching_Engine SHALL 允许设置手续费率和滑点模型
5. THE Matching_Engine SHALL 记录每笔成交的详细信息（时间、价格、数量、手续费、撮合模式）
6. THE Matching_Engine SHALL 在回测报告中提供撮合质量指标（成交率、滑点分布、队列等待时间）

### Requirement 8: 策略开发 IDE

**User Story:** As a 策略开发者, I want 内置的代码编辑器和热重载功能, so that 我可以快速迭代策略逻辑。

#### Acceptance Criteria

1. THE Strategy_Lab SHALL 提供基于 Monaco Editor 的代码编辑器，支持 Python 语法高亮和自动补全
2. WHEN 策略类定义 parameters 字典, THEN THE Strategy_Lab SHALL 自动映射为 UI 表单（数字滑块、下拉选择）
3. WHEN 用户修改策略代码并点击"Reload", THEN THE Strategy_Lab SHALL 根据 Hot_Reload_Policy 执行热重载：
   - RESET 模式: 重新实例化策略，所有变量重置为初始值
   - PRESERVE 模式: 保留所有状态变量，仅更新方法逻辑
   - SELECTIVE 模式: 用户通过 @preserve 装饰器标记需要保留的变量
4. WHEN 热重载执行, THEN THE Strategy_Lab SHALL 在日志中明确记录重载模式和受影响的变量列表
5. IF 热重载导致策略状态不一致, THEN THE Strategy_Lab SHALL 提示用户并提供"回滚到重载前状态"选项
6. THE Strategy_Lab SHALL 提供策略模板（继承 CtaTemplate），包含标准生命周期方法

### Requirement 9: 参数优化

**User Story:** As a 量化研究员, I want 智能参数优化功能, so that 我可以找到最优策略参数组合。

#### Acceptance Criteria

1. THE Optimizer SHALL 集成 Optuna，支持贝叶斯优化和遗传算法
2. WHEN 用户选择参数范围和优化目标, THEN THE Optimizer SHALL 自动搜索最优参数组合
3. THE Optimizer SHALL 支持 Sharpe Ratio、Total Return 等多种优化目标
4. WHEN 优化完成, THEN THE Optimizer SHALL 提供参数敏感性热力图可视化
5. THE Optimization_Mode SHALL 采用多进程并行执行，每个进程拥有独立的策略实例和数据副本
6. THE Optimization_Mode SHALL 保证进程间完全隔离，一个进程的崩溃不影响其他进程
7. THE Backtest_Mode SHALL 采用单线程顺序执行，保证结果的确定性和可重现性
8. WHEN 从 Backtest_Mode 切换到 Optimization_Mode, THEN THE Titan_Quant_System SHALL 明确提示用户并发模型的差异

### Requirement 10: 风控与熔断

**User Story:** As a 风控经理, I want 自动熔断机制, so that 系统可以在异常情况下保护资金安全。

#### Acceptance Criteria

1. WHEN 单日回撤超过配置阈值 X%, THEN THE Risk_Controller SHALL 强制停止策略并平仓
2. WHEN 单笔亏损超过配置阈值 Y%, THEN THE Risk_Controller SHALL 强制停止策略并平仓
3. THE Risk_Controller SHALL 从 risk_control.yaml 读取风控阈值配置
4. WHEN 风控触发, THEN THE Risk_Controller SHALL 记录触发原因和当时的市场状态

### Requirement 11: 通知系统

**User Story:** As a 用户, I want 多渠道通知功能, so that 我可以及时收到重要事件提醒。

#### Acceptance Criteria

1. THE Titan_Quant_System SHALL 支持 SMTP 邮件通知
2. THE Titan_Quant_System SHALL 支持 Webhook 通知（飞书/钉钉）
3. THE Titan_Quant_System SHALL 区分两种告警类型：
   - Sync_Alert（同步告警）: 阻塞当前流程直到用户确认，用于风控熔断、关键错误
   - Async_Alert（异步告警）: 不阻塞流程，后台发送，用于状态通知、定期报告
4. WHEN 策略报错或触发风控, THEN THE UI_Client SHALL 发送 Sync_Alert，弹出原生系统通知并等待确认
5. WHEN 回测完成或定时报告, THEN THE Titan_Quant_System SHALL 发送 Async_Alert
6. THE Titan_Quant_System SHALL 允许用户为每种事件类型配置告警级别（Sync/Async）和通知渠道

### Requirement 12: 用户认证与权限

**User Story:** As a 系统管理员, I want 多用户认证和权限管理, so that 我可以控制不同用户的访问权限。

#### Acceptance Criteria

1. THE UI_Client SHALL 提供本地登录界面
2. THE Titan_Quant_System SHALL 支持创建多用户（Admin/Trader 角色）
3. WHEN 用户登录, THEN THE Titan_Quant_System SHALL 验证密码并解密本地 KeyStore
4. THE Titan_Quant_System SHALL 根据用户角色限制功能访问

### Requirement 13: 敏感数据加密

**User Story:** As a 用户, I want 敏感数据加密存储, so that 我的 API Key 和密码不会泄露。

#### Acceptance Criteria

1. THE Titan_Quant_System SHALL 使用 Fernet 对称加密存储 API Key 和邮箱密码
2. THE Titan_Quant_System SHALL 将加密密钥存储在独立的 keyfile.key 文件中
3. WHEN 读取敏感配置, THEN THE Titan_Quant_System SHALL 在内存中解密，不在日志中输出明文

### Requirement 14: 审计日志

**User Story:** As a 合规人员, I want 完整的操作审计日志, so that 我可以追溯所有关键操作。

#### Acceptance Criteria

1. THE Audit_Logger SHALL 使用 RotatingFileHandler 实现线程安全的日志写入
2. WHEN 用户执行手动平仓操作, THEN THE Audit_Logger SHALL 记录 IP、时间、操作详情
3. WHEN 用户修改策略参数, THEN THE Audit_Logger SHALL 记录修改前值和修改后值
4. THE Audit_Logger SHALL 将交易审计日志写入 trading_audit.log
5. THE Audit_Logger SHALL 将用户操作日志写入 user_action.log
6. THE Audit_Logger SHALL 为每条审计记录生成 SHA-256 Hash，包含前一条记录的 Hash（链式哈希）
7. THE Audit_Logger SHALL 在日志文件末尾维护 Checksum，用于检测日志篡改
8. WHEN 系统启动, THEN THE Audit_Logger SHALL 验证审计日志的完整性，IF 检测到篡改, THEN SHALL 发送 Sync_Alert 并拒绝启动

### Requirement 15: 回测报告生成

**User Story:** As a 量化研究员, I want 自动生成交互式回测报告, so that 我可以分析和分享回测结果。

#### Acceptance Criteria

1. WHEN 回测结束, THEN THE Titan_Quant_System SHALL 自动生成交互式 HTML 报告
2. THE 报告 SHALL 包含夏普比率、最大回撤、总收益等关键指标
3. THE 报告 SHALL 包含资金曲线图和逐笔成交单（trades.csv）
4. THE Titan_Quant_System SHALL 将报告保存到 reports/ 目录，按实验编号分类
