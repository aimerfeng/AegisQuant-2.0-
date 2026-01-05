# Titan-Quant

工程级量化交易回测系统，采用守护进程+GUI客户端分离架构。

## 特性

- **事件驱动架构**: 高性能回测引擎，保证事件顺序确定性
- **L1/L2 撮合**: 支持多种撮合模式，L2 模式声明模拟等级
- **策略热重载**: 支持 RESET/PRESERVE/SELECTIVE 三种重载策略
- **完整风控**: 自动熔断机制，保护资金安全
- **审计日志**: 链式哈希校验，不可篡改
- **类 TradingView UI**: 专业 K 线图和多窗口布局

## 项目结构

```
titan-quant/
├── bin/                    # 启动脚本
├── config/                 # 配置文件
│   ├── i18n/              # 国际化语言包
│   ├── system_setting.yaml
│   └── risk_control.yaml
├── core/                   # 核心引擎
│   ├── engine/            # 事件总线、撮合引擎等
│   │   └── adapters/      # 引擎适配器
│   ├── data/              # 数据治理
│   │   └── providers/     # 数据源插件
│   └── strategies/        # 策略管理
├── database/              # 数据存储
│   ├── ticks/            # Tick 数据
│   ├── bars/             # K 线数据
│   └── cache/            # 缓存
├── logs/                  # 日志文件
├── reports/               # 回测报告
├── strategies/            # 用户策略
├── ui/                    # Electron + React 前端
└── utils/                 # 工具模块
```

## 安装

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .
```

## 快速开始

```bash
# 启动后端服务
python -m core.server

# 启动前端 (另一个终端)
cd ui && npm start
```

## 技术栈

- **后端**: Python 3.10+, VeighNa, TA-Lib, Optuna, Polars
- **前端**: Electron, React, TypeScript, Lightweight-charts
- **数据库**: SQLite (元数据), Parquet (行情数据)
- **测试**: pytest, hypothesis (属性测试)

## 许可证

MIT License
