# Design Document: Titan-Quant

## Overview

Titan-Quant 采用守护进程+GUI客户端分离的微服务架构，通过事件驱动模式实现高性能回测。系统核心设计原则：

1. **解耦与可扩展性**: 通过 Engine_Adapter 接口与底层交易框架解耦，通过 Data_Provider 接口与数据源解耦
2. **确定性保证 (Determinism)**: Event_Bus 保证事件顺序严格单调递增，确保回测结果 100% 可重现
3. **状态可恢复 (Crash Recovery)**: 完整的 Snapshot 机制支持断点恢复和状态回溯
4. **安全与审计**: 链式哈希审计日志，敏感数据 (API Keys) 独立加密存储
5. **高性能计算**: 核心计算层支持 C++/Rust 扩展，Python 层仅负责逻辑调度
6. **国际化支持**: 后端生成 I18N Keys，前端负责翻译，支持动态语言切换

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Titan-Quant System                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         UI Layer (Electron + React)                  │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │    │
│  │  │  KLine_Chart │  │  Strategy_   │  │  OrderBook   │  │  Control │ │    │
│  │  │  (WebGL)     │  │  Lab         │  │  Depth       │  │  Panel   │ │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘ │    │
│  │                    Golden-Layout Multi-Window Manager                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                          WebSocket / ZMQ                                     │
│                                    │                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Core Engine (Python Daemon)                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │                        Event_Bus                              │   │    │
│  │  │  (Deterministic Event Queue with Monotonic Sequence Numbers)  │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  │           │              │              │              │             │    │
│  │  ┌────────▼───────┐ ┌────▼─────┐ ┌─────▼─────┐ ┌──────▼──────┐     │    │
│  │  │ Engine_Adapter │ │ Matching │ │  Replay   │ │    Risk     │     │    │
│  │  │ (VeighNa/自研) │ │  Engine  │ │ Controller│ │  Controller │     │    │
│  │  └────────────────┘ └──────────┘ └───────────┘ └─────────────┘     │    │
│  │           │                                                         │    │
│  │  ┌────────▼───────┐ ┌───────────┐ ┌───────────┐ ┌─────────────┐   │    │
│  │  │ Data_Governance│ │ Strategy  │ │ Optimizer │ │   Audit     │   │    │
│  │  │     Hub        │ │  Manager  │ │ (Optuna)  │ │   Logger    │   │    │
│  │  └────────────────┘ └───────────┘ └───────────┘ └─────────────┘   │    │
│  │           │                                                         │    │
│  │  ┌────────▼───────────────────────────────────────────────────┐   │    │
│  │  │              Abstract_Data_Provider (Plugin Interface)      │   │    │
│  │  │         MySQL | MongoDB | DolphinDB | Parquet Local         │   │    │
│  │  └────────────────────────────────────────────────────────────┘   │    │
│  │           │                                                         │    │
│  │  ┌────────▼───────┐                                               │    │
│  │  │  I18n_Manager  │                                               │    │
│  │  └────────────────┘                                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Data Layer                                   │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    │
│  │  │   SQLite     │  │   Parquet    │  │      Snapshot Store      │  │    │
│  │  │  (Metadata)  │  │  (Tick/Bar)  │  │   (State Serialization)  │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │    │
│  │  ┌──────────────┐                                                   │    │
│  │  │ Encrypted    │                                                   │    │
│  │  │ KeyStore     │                                                   │    │
│  │  └──────────────┘                                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Event_Bus (事件总线)

事件总线是系统的核心，负责所有组件间的消息传递，保证事件处理的确定性。

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
import threading

class EventType(Enum):
    TICK = "tick"
    BAR = "bar"
    ORDER = "order"
    TRADE = "trade"
    POSITION = "position"
    ACCOUNT = "account"
    STRATEGY = "strategy"
    RISK = "risk"
    SYSTEM = "system"

@dataclass
class Event:
    """事件基类，包含单调递增序号保证确定性"""
    sequence_number: int          # 单调递增序号
    event_type: EventType
    timestamp: datetime           # 事件时间戳
    data: Any                     # 事件数据
    source: str                   # 事件来源

class IEventBus(ABC):
    """事件总线接口"""
    
    @abstractmethod
    def publish(self, event_type: EventType, data: Any, source: str) -> int:
        """发布事件，返回事件序号"""
        pass
    
    @abstractmethod
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> str:
        """订阅事件，返回订阅ID"""
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        pass
    
    @abstractmethod
    def get_current_sequence(self) -> int:
        """获取当前事件序号"""
        pass
    
    @abstractmethod
    def replay_from(self, sequence_number: int) -> List[Event]:
        """从指定序号重放事件"""
        pass
    
    @abstractmethod
    def get_pending_events(self) -> List[Event]:
        """获取待处理事件队列"""
        pass
```

### 2. Engine_Adapter (引擎适配器)

通过适配器模式解耦底层框架，支持 VeighNa、自研引擎等多种实现。

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class BarData:
    """K线数据"""
    symbol: str
    exchange: str
    datetime: datetime
    interval: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    turnover: float

@dataclass
class TickData:
    """Tick数据"""
    symbol: str
    exchange: str
    datetime: datetime
    last_price: float
    volume: float
    bid_price_1: float
    bid_volume_1: float
    ask_price_1: float
    ask_volume_1: float
    # L2 数据扩展
    bid_prices: Optional[List[float]] = None  # 买1-10价格
    bid_volumes: Optional[List[float]] = None
    ask_prices: Optional[List[float]] = None  # 卖1-10价格
    ask_volumes: Optional[List[float]] = None

@dataclass
class OrderData:
    """订单数据"""
    order_id: str
    symbol: str
    exchange: str
    direction: str          # "LONG" | "SHORT"
    offset: str             # "OPEN" | "CLOSE"
    price: float
    volume: float
    traded: float
    status: str             # "PENDING" | "FILLED" | "CANCELLED"
    is_manual: bool         # 是否人工干预单
    create_time: datetime

class IEngineAdapter(ABC):
    """引擎适配器接口"""
    
    @abstractmethod
    def initialize(self, config: Dict) -> bool:
        """初始化引擎"""
        pass
    
    @abstractmethod
    def load_strategy(self, strategy_class: type, params: Dict) -> str:
        """加载策略，返回策略ID"""
        pass
    
    @abstractmethod
    def start_backtest(self, start_date: datetime, end_date: datetime) -> bool:
        """启动回测"""
        pass
    
    @abstractmethod
    def pause(self) -> bool:
        """暂停回测"""
        pass
    
    @abstractmethod
    def resume(self) -> bool:
        """恢复回测"""
        pass
    
    @abstractmethod
    def step(self) -> bool:
        """单步执行"""
        pass
    
    @abstractmethod
    def get_engine_name(self) -> str:
        """获取引擎名称"""
        pass
```

### 3. Matching_Engine (撮合引擎)

支持 L1/L2 撮合模式，L2 模式需声明模拟等级。

```python
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

class MatchingMode(Enum):
    L1 = "L1"  # 基于对价成交，假设无限流动性
    L2 = "L2"  # 基于订单簿

class L2SimulationLevel(Enum):
    LEVEL_1 = "queue_position"      # 队列位置估算
    LEVEL_2 = "orderbook_rebuild"   # 完整订单簿重建
    LEVEL_3 = "microstructure"      # 市场微观结构模拟

@dataclass
class MatchingConfig:
    """撮合配置"""
    mode: MatchingMode
    l2_level: Optional[L2SimulationLevel] = None
    commission_rate: float = 0.0003      # 手续费率
    slippage_model: str = "fixed"        # "fixed" | "volume_based" | "volatility_based"
    slippage_value: float = 0.0001       # 滑点值

@dataclass
class TradeRecord:
    """成交记录"""
    trade_id: str
    order_id: str
    symbol: str
    direction: str
    price: float
    volume: float
    commission: float
    slippage: float
    matching_mode: MatchingMode
    l2_level: Optional[L2SimulationLevel]
    queue_wait_time: Optional[float]     # L2模式下的队列等待时间
    timestamp: datetime

@dataclass
class MatchingQualityMetrics:
    """撮合质量指标"""
    fill_rate: float                     # 成交率
    avg_slippage: float                  # 平均滑点
    slippage_distribution: Dict[str, float]  # 滑点分布
    avg_queue_wait_time: Optional[float] # 平均队列等待时间

class IMatchingEngine(ABC):
    """撮合引擎接口"""
    
    @abstractmethod
    def configure(self, config: MatchingConfig) -> None:
        """配置撮合参数"""
        pass
    
    @abstractmethod
    def submit_order(self, order: OrderData) -> str:
        """提交订单，返回订单ID"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        pass
    
    @abstractmethod
    def process_tick(self, tick: TickData) -> List[TradeRecord]:
        """处理Tick数据，返回成交记录"""
        pass
    
    @abstractmethod
    def get_quality_metrics(self) -> MatchingQualityMetrics:
        """获取撮合质量指标"""
        pass
    
    @abstractmethod
    def get_simulation_limitations(self) -> str:
        """获取当前模拟等级的局限性说明"""
        pass
```

### 4. Snapshot_Manager (快照管理器)

完整的状态快照机制，支持断点恢复。

```python
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

@dataclass
class AccountState:
    """账户状态"""
    cash: float                    # 现金
    frozen_margin: float           # 已用保证金
    available_balance: float       # 可用余额

@dataclass
class PositionState:
    """持仓状态"""
    symbol: str
    direction: str
    volume: float
    cost_price: float
    unrealized_pnl: float

@dataclass
class StrategyState:
    """策略状态"""
    strategy_id: str
    class_name: str
    parameters: Dict[str, Any]
    variables: Dict[str, Any]      # 所有状态变量

@dataclass
class Snapshot:
    """系统快照"""
    version: str                   # 快照版本号
    snapshot_id: str
    create_time: datetime
    
    # 账户与持仓
    account: AccountState
    positions: List[PositionState]
    
    # 策略状态
    strategies: List[StrategyState]
    
    # 事件总线状态
    event_sequence: int            # 当前事件序号
    pending_events: List[Dict]     # 待处理事件队列
    
    # 数据流位置
    data_timestamp: datetime       # 数据时间戳
    data_index: int                # 数据索引位置

class ISnapshotManager(ABC):
    """快照管理器接口"""
    
    CURRENT_VERSION = "1.0.0"
    
    @abstractmethod
    def create_snapshot(self) -> Snapshot:
        """创建当前状态快照"""
        pass
    
    @abstractmethod
    def save_snapshot(self, snapshot: Snapshot, path: str) -> bool:
        """保存快照到磁盘"""
        pass
    
    @abstractmethod
    def load_snapshot(self, path: str) -> Optional[Snapshot]:
        """从磁盘加载快照"""
        pass
    
    @abstractmethod
    def restore_snapshot(self, snapshot: Snapshot) -> bool:
        """恢复快照状态"""
        pass
    
    @abstractmethod
    def is_compatible(self, snapshot: Snapshot) -> bool:
        """检查快照版本兼容性"""
        pass
```

### 5. Strategy_Manager (策略管理器)

支持热重载和多种重载策略。

```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Any, Set

class HotReloadPolicy(Enum):
    RESET = "reset"           # 重置所有变量
    PRESERVE = "preserve"     # 保留所有状态变量
    SELECTIVE = "selective"   # 用户指定保留的变量

@dataclass
class ReloadResult:
    """重载结果"""
    success: bool
    policy: HotReloadPolicy
    preserved_variables: List[str]
    reset_variables: List[str]
    error_message: Optional[str] = None

@dataclass
class StrategyParameter:
    """策略参数定义"""
    name: str
    param_type: str           # "int" | "float" | "string" | "enum"
    default_value: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    options: Optional[List[Any]] = None  # enum类型的选项
    ui_widget: str = "input"  # "input" | "slider" | "dropdown"

class IStrategyManager(ABC):
    """策略管理器接口"""
    
    @abstractmethod
    def load_strategy_file(self, file_path: str) -> bool:
        """加载策略文件"""
        pass
    
    @abstractmethod
    def get_parameters(self, strategy_id: str) -> List[StrategyParameter]:
        """获取策略参数定义"""
        pass
    
    @abstractmethod
    def set_parameters(self, strategy_id: str, params: Dict[str, Any]) -> bool:
        """设置策略参数"""
        pass
    
    @abstractmethod
    def hot_reload(self, strategy_id: str, policy: HotReloadPolicy, 
                   preserve_vars: Optional[Set[str]] = None) -> ReloadResult:
        """热重载策略"""
        pass
    
    @abstractmethod
    def rollback(self, strategy_id: str) -> bool:
        """回滚到重载前状态"""
        pass
    
    @abstractmethod
    def get_state_variables(self, strategy_id: str) -> Dict[str, Any]:
        """获取策略状态变量"""
        pass
```

### 6. Audit_Logger (审计日志)

链式哈希审计日志，保证不可篡改。

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
import hashlib

@dataclass
class AuditRecord:
    """审计记录"""
    record_id: str
    timestamp: datetime
    user_id: str
    ip_address: str
    action_type: str           # "MANUAL_TRADE" | "PARAM_CHANGE" | "STRATEGY_RELOAD" | ...
    action_detail: Dict[str, Any]
    previous_value: Optional[Any]
    new_value: Optional[Any]
    previous_hash: str         # 前一条记录的哈希
    record_hash: str           # 当前记录的哈希

class IAuditLogger(ABC):
    """审计日志接口"""
    
    @abstractmethod
    def log_trade(self, user_id: str, ip: str, trade: TradeRecord, 
                  is_manual: bool) -> str:
        """记录交易"""
        pass
    
    @abstractmethod
    def log_param_change(self, user_id: str, ip: str, strategy_id: str,
                         param_name: str, old_value: Any, new_value: Any) -> str:
        """记录参数修改"""
        pass
    
    @abstractmethod
    def log_action(self, user_id: str, ip: str, action_type: str,
                   detail: Dict[str, Any]) -> str:
        """记录通用操作"""
        pass
    
    @abstractmethod
    def verify_integrity(self) -> bool:
        """验证日志完整性"""
        pass
    
    @abstractmethod
    def get_checksum(self) -> str:
        """获取日志文件校验和"""
        pass
    
    @abstractmethod
    def compute_record_hash(self, record: AuditRecord) -> str:
        """计算记录哈希"""
        pass
```

### 7. Alert_System (告警系统)

区分同步和异步告警。

```python
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Callable

class AlertType(Enum):
    SYNC = "sync"     # 同步告警，阻塞流程
    ASYNC = "async"   # 异步告警，不阻塞

class AlertChannel(Enum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    SYSTEM_NOTIFICATION = "system_notification"

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class AlertConfig:
    """告警配置"""
    event_type: str
    alert_type: AlertType
    channels: List[AlertChannel]
    severity: AlertSeverity

@dataclass
class Alert:
    """告警消息"""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    acknowledged: bool = False

class IAlertSystem(ABC):
    """告警系统接口"""
    
    @abstractmethod
    def send_sync_alert(self, title: str, message: str, 
                        severity: AlertSeverity) -> bool:
        """发送同步告警，阻塞直到用户确认"""
        pass
    
    @abstractmethod
    def send_async_alert(self, title: str, message: str,
                         severity: AlertSeverity, 
                         channels: List[AlertChannel]) -> str:
        """发送异步告警，返回告警ID"""
        pass
    
    @abstractmethod
    def configure_event_alert(self, config: AlertConfig) -> bool:
        """配置事件告警规则"""
        pass
    
    @abstractmethod
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        pass
```

### 8. Data_Governance_Hub (数据治理中心)

数据导入、清洗和存储。

```python
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional
import pandas as pd

class FillMethod(Enum):
    FORWARD_FILL = "ffill"
    LINEAR = "linear"
    DROP = "drop"

class DataFormat(Enum):
    CSV = "csv"
    EXCEL = "excel"
    PARQUET = "parquet"
    SQL_DUMP = "sql"

@dataclass
class DataQualityReport:
    """数据质量报告"""
    total_rows: int
    missing_values: Dict[str, int]      # 列名 -> 缺失数量
    outliers: Dict[str, List[int]]      # 列名 -> 异常值行号
    timestamp_gaps: List[datetime]       # 时间戳缺口
    alignment_issues: List[str]          # 对齐问题描述

@dataclass
class CleaningConfig:
    """清洗配置"""
    fill_method: FillMethod
    outlier_threshold: float = 3.0       # 标准差倍数
    remove_outliers: bool = False
    align_timestamps: bool = True

class IDataGovernanceHub(ABC):
    """数据治理中心接口"""
    
    @abstractmethod
    def import_file(self, file_path: str, format: DataFormat) -> pd.DataFrame:
        """导入文件"""
        pass
    
    @abstractmethod
    def analyze_quality(self, df: pd.DataFrame) -> DataQualityReport:
        """分析数据质量"""
        pass
    
    @abstractmethod
    def clean_data(self, df: pd.DataFrame, config: CleaningConfig) -> pd.DataFrame:
        """清洗数据"""
        pass
    
    @abstractmethod
    def validate_alignment(self, dfs: List[pd.DataFrame]) -> List[str]:
        """验证多合约时间戳对齐"""
        pass
    
    @abstractmethod
    def save_to_parquet(self, df: pd.DataFrame, symbol: str, date: str) -> str:
        """保存为Parquet格式"""
        pass
```

### 9. Abstract_Data_Provider (数据源插件接口)

支持通过插件接入外部数据源（MySQL, MongoDB, DolphinDB 等）。

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime

@dataclass
class HistoryRequest:
    """历史数据请求"""
    symbol: str
    exchange: str
    start: datetime
    end: datetime
    interval: str              # "1m" | "5m" | "1h" | "1d" | "tick"

class AbstractDataProvider(ABC):
    """
    数据源抽象接口 (Plugin Interface)
    允许用户实现该接口以接入 MySQL, MongoDB, DolphinDB 或 API 数据源
    """
    
    @abstractmethod
    def connect(self, setting: Dict[str, Any]) -> bool:
        """连接数据源"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """断开连接"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass
    
    @abstractmethod
    def load_bar_history(self, req: HistoryRequest) -> List[BarData]:
        """加载 K 线历史数据"""
        pass
    
    @abstractmethod
    def load_tick_history(self, req: HistoryRequest) -> List[TickData]:
        """加载 Tick 历史数据"""
        pass
    
    @abstractmethod
    def get_available_symbols(self, exchange: str) -> List[str]:
        """获取可用合约列表"""
        pass
    
    @abstractmethod
    def get_dominant_contract(self, symbol_root: str) -> str:
        """获取主力合约"""
        pass
    
    @abstractmethod
    def download_and_cache(self, req: HistoryRequest, save_path: str) -> bool:
        """下载数据并缓存到本地 Parquet"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """获取数据源名称"""
        pass


# 内置实现示例
class ParquetDataProvider(AbstractDataProvider):
    """本地 Parquet 文件数据源"""
    pass

class MySQLDataProvider(AbstractDataProvider):
    """MySQL 数据源"""
    pass

class MongoDBDataProvider(AbstractDataProvider):
    """MongoDB 数据源"""
    pass

class DolphinDBDataProvider(AbstractDataProvider):
    """DolphinDB 数据源"""
    pass
```

### 10. I18n_Manager (国际化管理器)

后端负责生成 I18N Keys，支持动态语言切换。

```python
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Optional

class Language(Enum):
    EN = "en"
    ZH_CN = "zh_cn"
    ZH_TW = "zh_tw"
    JA = "ja"

@dataclass
class I18nConfig:
    """国际化配置"""
    default_language: Language
    fallback_language: Language = Language.EN
    language_pack_dir: str = "config/i18n"

class II18nManager(ABC):
    """后端国际化接口"""
    
    @abstractmethod
    def load_language_pack(self, lang: Language) -> bool:
        """加载语言包 JSON"""
        pass
    
    @abstractmethod
    def set_language(self, lang: Language) -> bool:
        """设置当前语言"""
        pass
    
    @abstractmethod
    def get_current_language(self) -> Language:
        """获取当前语言"""
        pass
    
    @abstractmethod
    def translate(self, key: str, **kwargs) -> str:
        """
        翻译文本，支持参数插值
        
        Example: 
            translate("error.insufficient_fund", required=100, available=50)
            -> "Insufficient funds: required 100, available 50"
        """
        pass
    
    @abstractmethod
    def get_all_keys(self) -> List[str]:
        """获取所有翻译键"""
        pass


# 语言包 JSON 结构示例
# config/i18n/zh_cn.json
"""
{
    "error": {
        "insufficient_fund": "资金不足：需要 {required}，可用 {available}",
        "order_rejected": "订单被拒绝：{reason}",
        "strategy_error": "策略执行错误：{message}"
    },
    "audit": {
        "manual_trade": "手动交易",
        "param_change": "参数修改",
        "strategy_reload": "策略重载"
    },
    "alert": {
        "risk_trigger": "风控触发：{reason}",
        "backtest_complete": "回测完成"
    }
}
"""
```

## Data Models

### 数据库 Schema (SQLite)

```sql
-- 用户表
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,      -- Argon2 hash
    role TEXT NOT NULL CHECK (role IN ('admin', 'trader')),
    settings TEXT,                     -- UI偏好设置 JSON
    preferred_language TEXT DEFAULT 'zh_cn',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- API 密钥表 (加密存储)
-- 注意：secret_key 必须存储加密后的密文
CREATE TABLE exchange_keys (
    key_id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(user_id),
    exchange TEXT NOT NULL,            -- "binance" | "okx" | "huobi"
    api_key_name TEXT NOT NULL,        -- 用户自定义名称
    api_key_ciphertext TEXT NOT NULL,  -- Fernet Encrypted
    secret_key_ciphertext TEXT NOT NULL, -- Fernet Encrypted
    passphrase_ciphertext TEXT,        -- Fernet Encrypted (部分交易所需要)
    permissions TEXT,                   -- JSON: ["read", "trade", "withdraw"]
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- 策略元数据表
CREATE TABLE strategies (
    strategy_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    class_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    parameters TEXT,                   -- JSON
    checksum TEXT NOT NULL,            -- 文件校验和，防止代码被篡改
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- 回测记录表
CREATE TABLE backtest_records (
    backtest_id TEXT PRIMARY KEY,
    strategy_id TEXT REFERENCES strategies(strategy_id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital REAL NOT NULL,
    matching_mode TEXT NOT NULL,
    l2_level TEXT,
    data_provider TEXT,                -- 数据源名称
    status TEXT NOT NULL CHECK (status IN ('running', 'paused', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 回测结果表
CREATE TABLE backtest_results (
    result_id TEXT PRIMARY KEY,
    backtest_id TEXT REFERENCES backtest_records(backtest_id),
    total_return REAL,
    sharpe_ratio REAL,
    max_drawdown REAL,
    win_rate REAL,
    profit_factor REAL,
    total_trades INTEGER,
    metrics_json TEXT,                 -- 完整指标 JSON
    report_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 快照表
CREATE TABLE snapshots (
    snapshot_id TEXT PRIMARY KEY,
    backtest_id TEXT REFERENCES backtest_records(backtest_id),
    version TEXT NOT NULL,
    file_path TEXT NOT NULL,
    data_timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 告警配置表
CREATE TABLE alert_configs (
    config_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    alert_type TEXT NOT NULL CHECK (alert_type IN ('sync', 'async')),
    channels TEXT NOT NULL,            -- JSON array
    severity TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE
);

-- 数据源配置表
CREATE TABLE data_providers (
    provider_id TEXT PRIMARY KEY,
    provider_type TEXT NOT NULL,       -- "parquet" | "mysql" | "mongodb" | "dolphindb"
    name TEXT NOT NULL,
    connection_config TEXT NOT NULL,   -- JSON (加密敏感字段)
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Parquet 数据结构

```
database/
├── ticks/
│   ├── binance/
│   │   ├── btc_usdt/
│   │   │   ├── 2024-01-01.parquet
│   │   │   │   Schema:
│   │   │   │   - timestamp: datetime64[ns]
│   │   │   │   - last_price: float64
│   │   │   │   - volume: float64
│   │   │   │   - bid_price_1..10: float64
│   │   │   │   - bid_volume_1..10: float64
│   │   │   │   - ask_price_1..10: float64
│   │   │   │   - ask_volume_1..10: float64
│   │   │   └── ...
│   │   └── eth_usdt/
│   └── okx/
├── bars/
│   ├── binance/
│   │   ├── btc_usdt/
│   │   │   ├── 1m.parquet
│   │   │   │   Schema:
│   │   │   │   - timestamp: datetime64[ns]
│   │   │   │   - open: float64
│   │   │   │   - high: float64
│   │   │   │   - low: float64
│   │   │   │   - close: float64
│   │   │   │   - volume: float64
│   │   │   │   - turnover: float64
│   │   │   ├── 5m.parquet
│   │   │   └── 1h.parquet
│   │   └── eth_usdt/
│   └── okx/
└── cache/                    # 数据源下载缓存
    └── ...
```

### 配置文件结构

```yaml
# config/system_setting.yaml
system:
  engine_adapter: "veighna"  # veighna | custom
  data_path: "./database"
  log_level: "INFO"

communication:
  protocol: "websocket"  # websocket | zmq
  host: "127.0.0.1"
  port: 8765

backtest:
  default_capital: 1000000
  default_commission: 0.0003
  default_slippage: 0.0001

optimization:
  max_workers: 4
  default_iterations: 100

# config/risk_control.yaml
risk:
  max_daily_drawdown: 0.05      # 5%
  max_single_loss: 0.02         # 2%
  max_position_ratio: 0.8       # 80%
  enable_auto_liquidation: true

alerts:
  risk_trigger:
    type: "sync"
    channels: ["system_notification", "email"]
    severity: "critical"
  backtest_complete:
    type: "async"
    channels: ["email"]
    severity: "info"
```


## Communication Protocol

### WebSocket 消息格式

```typescript
// 消息基础结构
interface Message {
  id: string;           // 消息唯一ID
  type: MessageType;
  timestamp: number;
  payload: any;
}

enum MessageType {
  // 控制消息
  CONNECT = "connect",
  DISCONNECT = "disconnect",
  HEARTBEAT = "heartbeat",
  
  // 回测控制
  START_BACKTEST = "start_backtest",
  PAUSE = "pause",
  RESUME = "resume",
  STEP = "step",
  STOP = "stop",
  
  // 数据推送
  TICK_UPDATE = "tick_update",
  BAR_UPDATE = "bar_update",
  POSITION_UPDATE = "position_update",
  ACCOUNT_UPDATE = "account_update",
  TRADE_UPDATE = "trade_update",
  
  // 策略操作
  LOAD_STRATEGY = "load_strategy",
  RELOAD_STRATEGY = "reload_strategy",
  UPDATE_PARAMS = "update_params",
  
  // 手动交易
  MANUAL_ORDER = "manual_order",
  CANCEL_ORDER = "cancel_order",
  CLOSE_ALL = "close_all",
  
  // 快照
  SAVE_SNAPSHOT = "save_snapshot",
  LOAD_SNAPSHOT = "load_snapshot",
  
  // 告警
  ALERT = "alert",
  ALERT_ACK = "alert_ack"
}

// 示例：启动回测
interface StartBacktestPayload {
  strategy_id: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  matching_config: {
    mode: "L1" | "L2";
    l2_level?: "LEVEL_1" | "LEVEL_2" | "LEVEL_3";
    commission_rate: number;
    slippage_model: string;
    slippage_value: number;
  };
  replay_speed: number;  // 1x, 2x, 4x, 10x
}

// 示例：手动下单
interface ManualOrderPayload {
  symbol: string;
  direction: "LONG" | "SHORT";
  offset: "OPEN" | "CLOSE";
  price: number;
  volume: number;
}
```

## UI Components

### 前端技术栈

- **框架**: Electron + React + TypeScript
- **状态管理**: Zustand
- **图表**: Lightweight-charts (TradingView)
- **布局**: Golden-Layout
- **编辑器**: Monaco Editor
- **通信**: WebSocket

### 组件结构

```
ui/src/
├── components/
│   ├── KLineChart/
│   │   ├── index.tsx           # K线图主组件
│   │   ├── DrawingTools.tsx    # 划线工具
│   │   ├── Indicators.tsx      # 指标面板
│   │   └── TradeMarkers.tsx    # 交易标记
│   ├── OrderBook/
│   │   ├── index.tsx           # 深度图组件
│   │   └── DepthChart.tsx      # 深度可视化
│   ├── StrategyLab/
│   │   ├── index.tsx           # 策略IDE主组件
│   │   ├── CodeEditor.tsx      # Monaco编辑器封装
│   │   └── ParamPanel.tsx      # 参数面板
│   ├── ControlPanel/
│   │   ├── index.tsx           # 控制面板
│   │   ├── PlaybackBar.tsx     # 播放控制条
│   │   └── ManualTrade.tsx     # 手动交易按钮
│   ├── DataCenter/
│   │   ├── index.tsx           # 数据中心
│   │   ├── FileDropzone.tsx    # 文件拖拽区
│   │   └── CleaningPreview.tsx # 清洗预览
│   └── Reports/
│       ├── index.tsx           # 报告组件
│       └── MetricsCard.tsx     # 指标卡片
├── layouts/
│   └── WorkspaceLayout.tsx     # Golden-Layout 布局管理
├── services/
│   ├── websocket.ts            # WebSocket 服务
│   └── api.ts                  # API 封装
├── stores/
│   ├── backtestStore.ts        # 回测状态
│   ├── strategyStore.ts        # 策略状态
│   └── alertStore.ts           # 告警状态
└── App.tsx
```

## Error Handling

### 错误分类

```python
class TitanQuantError(Exception):
    """基础异常类"""
    pass

class EngineError(TitanQuantError):
    """引擎错误"""
    pass

class DataError(TitanQuantError):
    """数据错误"""
    pass

class StrategyError(TitanQuantError):
    """策略错误"""
    pass

class SnapshotError(TitanQuantError):
    """快照错误"""
    pass

class AuditIntegrityError(TitanQuantError):
    """审计完整性错误"""
    pass

class RiskControlError(TitanQuantError):
    """风控错误"""
    pass
```

### 错误处理策略

| 错误类型 | 处理策略 | 告警类型 |
|---------|---------|---------|
| EngineError | 记录日志，尝试优雅降级 | Sync |
| DataError | 提示用户，暂停回测 | Async |
| StrategyError | 记录日志，提供回滚选项 | Sync |
| SnapshotError | 提示版本不兼容 | Async |
| AuditIntegrityError | 拒绝启动，强制告警 | Sync |
| RiskControlError | 强制平仓，暂停策略 | Sync |

## Testing Strategy

### 测试框架

- **Python 后端**: pytest + hypothesis (属性测试)
- **TypeScript 前端**: Jest + React Testing Library

### 测试分层

1. **单元测试**: 各组件独立测试
2. **集成测试**: 组件间交互测试
3. **属性测试**: 验证系统正确性属性
4. **端到端测试**: 完整流程测试


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the acceptance criteria analysis, the following correctness properties must be validated through property-based testing:

### Property 1: Event Sequence Monotonicity

*For any* sequence of events published to the Event_Bus, the sequence_number of each event must be strictly greater than the sequence_number of the previous event.

**Validates: Requirements 1.7**

### Property 2: Backtest Determinism

*For any* backtest configuration (strategy, data, parameters), running the backtest multiple times with identical inputs must produce identical event sequences and final results.

**Validates: Requirements 1.6, 9.7**

### Property 3: Data Format Detection

*For any* valid data file in supported formats (CSV, Excel, Parquet), the Data_Governance_Hub must correctly identify the format and successfully parse the data without data loss.

**Validates: Requirements 2.1**

### Property 4: Missing Value Fill Correctness

*For any* dataset with missing values, after applying Forward Fill or Linear interpolation, the resulting dataset must have no missing values, and filled values must conform to the selected fill strategy.

**Validates: Requirements 2.2**

### Property 5: Outlier Detection Accuracy

*For any* dataset, all values marked as outliers must have an absolute z-score greater than 3.0 (or the configured threshold), and no unmarked values should exceed this threshold.

**Validates: Requirements 2.3**

### Property 6: Timestamp Alignment Validation

*For any* set of multi-contract data, the alignment validation function must correctly identify all timestamp misalignments where corresponding data points do not exist across all contracts.

**Validates: Requirements 2.4**

### Property 7: Data Persistence Round-Trip

*For any* valid DataFrame, saving to Parquet format and reading back must produce an equivalent DataFrame with identical schema and values.

**Validates: Requirements 2.6**

### Property 8: Layout Persistence Round-Trip

*For any* valid workspace layout configuration, saving and loading the layout must restore the exact same window arrangement and component positions.

**Validates: Requirements 4.3, 4.4**

### Property 9: Single Step Precision

*For any* backtest state, executing a single step must advance the simulation by exactly one time unit (tick or bar interval) and process exactly the events for that time unit.

**Validates: Requirements 5.3**

### Property 10: Snapshot Round-Trip

*For any* valid backtest state, creating a snapshot and restoring from it must produce an identical state including account balance, positions, strategy variables, event queue position, and data stream position.

**Validates: Requirements 5.5, 5.6**

### Property 11: Manual Order Marking

*For any* order submitted through the manual trading interface, the order must have is_manual=true, and the corresponding audit log entry must be categorized as "MANUAL_TRADE" distinct from "AUTO_TRADE".

**Validates: Requirements 6.2, 6.3**

### Property 12: Close All Positions

*For any* non-empty position set, executing "close all" must result in an empty position set with all positions properly closed at market price.

**Validates: Requirements 6.4**

### Property 13: Trade Record Completeness

*For any* executed trade, the TradeRecord must contain all required fields: trade_id, order_id, symbol, direction, price, volume, commission, slippage, matching_mode, and timestamp.

**Validates: Requirements 7.5**

### Property 14: Strategy Parameter Mapping

*For any* strategy class with a parameters dictionary, the Strategy_Lab must generate a corresponding UI form configuration with correct widget types (slider for numeric ranges, dropdown for enums).

**Validates: Requirements 8.2**

### Property 15: Hot Reload Policy Compliance

*For any* hot reload operation with a specified policy (RESET/PRESERVE/SELECTIVE), the resulting strategy state must correctly reflect the policy: RESET clears all variables, PRESERVE keeps all variables, SELECTIVE keeps only @preserve-decorated variables.

**Validates: Requirements 8.3**

### Property 16: Optimizer Parameter Bounds

*For any* optimization result, all parameter values in the result must fall within the user-specified parameter ranges.

**Validates: Requirements 9.2**

### Property 17: Risk Control Trigger

*For any* account state where daily drawdown exceeds X% or single trade loss exceeds Y%, the Risk_Controller must trigger a circuit breaker, stop the strategy, and initiate position liquidation.

**Validates: Requirements 10.1, 10.2**

### Property 18: Alert Type Classification

*For any* alert event, the alert must be correctly classified as Sync_Alert (blocking) or Async_Alert (non-blocking) based on the configured alert rules.

**Validates: Requirements 11.3**

### Property 19: Role-Based Access Control

*For any* user with a specific role (Admin/Trader) and any protected function, the access control check must correctly permit or deny access based on the role's permissions.

**Validates: Requirements 12.4**

### Property 20: Sensitive Data Encryption Round-Trip

*For any* sensitive data (API keys, passwords), encrypting with Fernet and decrypting must produce the original plaintext.

**Validates: Requirements 13.1**

### Property 21: Sensitive Data Log Exclusion

*For any* log output generated during sensitive data operations, the log content must not contain any plaintext sensitive data (API keys, passwords).

**Validates: Requirements 13.3**

### Property 22: Audit Record Completeness

*For any* auditable operation (manual trade, parameter change), the audit record must contain: user_id, ip_address, timestamp, action_type, and for parameter changes, both previous_value and new_value.

**Validates: Requirements 14.2, 14.3**

### Property 23: Audit Chain Hash Integrity

*For any* sequence of audit records, each record's hash must be computed from the record content combined with the previous record's hash, forming an unbroken chain.

**Validates: Requirements 14.6**

### Property 24: Audit Integrity Verification

*For any* audit log file, if any record has been modified or deleted, the integrity verification must detect the tampering and return false.

**Validates: Requirements 14.8**

### Property 25: Report Metrics Completeness

*For any* completed backtest, the generated report must contain all required metrics: sharpe_ratio, max_drawdown, total_return, win_rate, profit_factor, and total_trades.

**Validates: Requirements 15.2**
