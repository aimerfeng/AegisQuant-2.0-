# Task 39.1: Zustand Store 实现

## 日期
2026-01-06

## 任务描述
实现前端状态管理的 Zustand Store，包括 backtestStore 和 strategyStore。

## 实现内容

### 1. backtestStore (ui/src/renderer/stores/backtestStore.ts)
回测状态管理 Store，负责：
- 回测生命周期管理 (IDLE → LOADING → RUNNING → PAUSED → COMPLETED)
- 播放控制 (play/pause/speed/progress)
- 实时数据更新 (tick/bar/account/positions/trades)
- 回测结果指标存储

**主要功能：**
- `startBacktest(config)` - 启动回测
- `play()` / `pause()` - 播放控制
- `setPlaybackSpeed(speed)` - 设置播放速度 (1x/2x/4x/10x)
- `updateTick()` / `updateBar()` - 更新市场数据
- `updateAccount()` / `updatePositions()` - 更新账户状态
- `addTrade()` - 添加成交记录

### 2. strategyStore (ui/src/renderer/stores/strategyStore.ts)
策略状态管理 Store，负责：
- 策略列表管理
- 策略实例生命周期
- 参数管理
- 热重载状态
- 代码编辑器文件管理

**主要功能：**
- `loadStrategy()` / `unloadStrategy()` - 策略加载/卸载
- `updateParameter()` / `updateParameters()` - 参数更新
- `startReload()` / `completeReload()` / `rollback()` - 热重载
- `openFile()` / `closeFile()` / `updateFileContent()` - 文件管理

### 3. stores/index.ts
创建统一的 Store 导出索引文件，方便组件导入。

### 4. layoutStore 修复
- 修复 `substr` 弃用警告，改用 `substring`
- 修复 Golden-Layout header 配置类型错误

## 已存在的 Stores
- `alertStore.ts` - 告警状态管理 ✓
- `i18nStore.ts` - 国际化状态管理 ✓
- `connectionStore.ts` - WebSocket 连接状态 ✓
- `layoutStore.ts` - 布局状态管理 ✓
- `authStore.ts` - 认证状态管理 ✓

## 改动文件
- `ui/src/renderer/stores/backtestStore.ts` (新增)
- `ui/src/renderer/stores/strategyStore.ts` (新增)
- `ui/src/renderer/stores/index.ts` (新增)
- `ui/src/renderer/stores/layoutStore.ts` (修复类型错误)

## 已知问题

### TypeScript 类型警告 (layoutStore.ts)
Golden-Layout 的 header 配置类型定义与实际使用不完全匹配，已简化配置以避免类型错误。

## 满足的需求
- Requirements: UI 状态管理
- 5.1: Replay_Controller 播放控制
- 8.2: 策略参数 UI 映射
- 8.3: 策略热重载

## 下一步
- Task 40: 前后端集成 - 将 Stores 与 WebSocket 服务连接
