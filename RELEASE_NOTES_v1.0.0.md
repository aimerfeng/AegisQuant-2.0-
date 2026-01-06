# Titan-Quant v1.0.0 Release Notes

## 🎉 首个正式版本发布！

Titan-Quant 是一个专业级量化交易回测系统，采用守护进程+GUI客户端分离架构。

## ✨ 主要功能

### 核心引擎
- 事件驱动回测引擎，保证事件顺序确定性
- L1/L2 撮合模式支持
- 策略热重载（RESET/PRESERVE/SELECTIVE）
- 完整风控系统，自动熔断机制
- 审计日志，链式哈希校验

### 用户界面
- 专业 K 线图表（基于 Lightweight-charts）
- 策略实验室（Monaco Editor 代码编辑器）
- 数据中心（CSV/Excel/Parquet 导入）
- 订单簿深度图
- 持仓和交易记录面板
- 实时日志查看
- 回测报告（夏普比率、最大回撤等指标）
- 多语言支持（简体中文、繁体中文、英文）

## 📦 下载

- **Windows 安装包**: `Titan-Quant Setup 1.0.0.exe`
- **Windows 便携版**: `win-unpacked.zip`（解压后运行 Titan-Quant.exe）

## 🚀 快速开始

1. 下载并安装 `Titan-Quant Setup 1.0.0.exe`
2. 安装 Python 3.10+ 并运行后端服务：
   ```bash
   pip install -r requirements.txt
   python -m core --debug
   ```
3. 启动 Titan-Quant 桌面应用

## 📋 系统要求

- Windows 10 或更高版本
- Python 3.10+
- 4GB RAM（推荐 8GB）
- 500MB 磁盘空间

## 🐛 已知问题

- Golden Layout 集成暂时禁用，使用简化的 Tab 布局
- 部分组件显示 Mock 数据，需要后端连接

## 📝 更新日志

查看完整更新日志：[CHANGELOG.md](CHANGELOG.md)

---

感谢使用 Titan-Quant！如有问题请提交 Issue。
