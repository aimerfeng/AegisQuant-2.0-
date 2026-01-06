# Task 29: 前端布局系统

**日期**: 2026-01-06
**提交**: [Task 29] 前端布局系统 - Golden-Layout 集成与布局持久化

## 概述

实现基于 Golden-Layout 的多窗口布局系统，支持拖拽、吸附、分屏功能，以及布局预设的保存和加载。

## 功能实现

### 29.1 Golden-Layout 集成
- 创建 `WorkspaceLayout.tsx` 主布局组件
- 实现多窗口拖拽、吸附、分屏功能
- 创建面板类型定义 (K线图、订单簿、策略实验室、日志、持仓、交易、控制面板、数据中心、报告)
- 实现 Zustand 布局状态管理
- 创建占位面板组件和面板工厂
- 添加 Golden-Layout 深色主题样式

### 29.2 布局持久化
- 实现 localStorage 布局保存/加载
- 实现预设管理 (保存/加载/删除)
- 实现布局 JSON 导入/导出
- 创建布局工具栏组件
- 添加多语言支持 (英文/简体中文/繁体中文)

### 29.3 属性测试
- Property 8: Layout Persistence Round-Trip
- 使用 fast-check 库实现属性测试
- 7 个测试全部通过 (100 次迭代/测试)

## 满足需求

- Requirements 4.1: 基于 Golden-Layout 实现多窗口拖拽、吸附、分屏功能
- Requirements 4.2: 支持将 K 线图、日志、深度图等组件自由排列
- Requirements 4.3: 支持将当前布局存储为"工作区预设"
- Requirements 4.4: 支持恢复之前保存的窗口布局

## 新增文件

```
ui/src/renderer/
├── types/
│   └── layout.ts                    # 布局类型定义
├── stores/
│   └── layoutStore.ts               # 布局状态管理
├── layouts/
│   ├── index.ts                     # 布局导出
│   ├── WorkspaceLayout.tsx          # 主布局组件
│   └── WorkspaceLayout.css          # 布局样式
├── components/
│   ├── panels/
│   │   ├── index.ts                 # 面板导出
│   │   ├── PlaceholderPanel.tsx     # 占位面板
│   │   ├── PlaceholderPanel.css     # 占位面板样式
│   │   └── panelFactory.tsx         # 面板工厂
│   ├── LayoutToolbar.tsx            # 布局工具栏
│   └── LayoutToolbar.css            # 工具栏样式
├── utils/
│   ├── index.ts                     # 工具导出
│   └── layoutPersistence.ts         # 布局持久化工具
└── __tests__/
    └── layoutPersistence.test.ts    # 属性测试
```

## 修改文件

- `ui/src/renderer/components/MainLayout.tsx` - 集成布局工具栏
- `ui/src/renderer/components/MainLayout.css` - 更新样式
- `ui/src/renderer/i18n/locales/en.json` - 添加布局翻译
- `ui/src/renderer/i18n/locales/zh_cn.json` - 添加布局翻译
- `ui/src/renderer/i18n/locales/zh_tw.json` - 添加布局翻译
- `ui/package.json` - 添加测试依赖
- `CHANGELOG.md` - 更新日志

## 测试结果

```
 PASS  src/renderer/__tests__/layoutPersistence.test.ts (12.442 s)
  Layout Persistence Property Tests
    Property 8: Layout Persistence Round-Trip
      √ should preserve layout data through export/import cycle (222 ms)
      √ should preserve layout config through clone operation (33 ms)
      √ should correctly validate layout configs (18 ms)
      √ should reject invalid layout configs (1 ms)
      √ should handle JSON parsing errors gracefully (69 ms)
      √ should preserve preset metadata through round-trip (79 ms)
      √ should preserve component state through round-trip (27 ms)

Test Suites: 1 passed, 1 total
Tests:       7 passed, 7 total
```

## 技术栈

- Golden-Layout 2.6.0 - 多窗口布局管理
- Zustand 4.4.7 - 状态管理
- fast-check 3.15.0 - 属性测试
- React 18.2.0 - UI 框架
- TypeScript 5.3.0 - 类型安全
