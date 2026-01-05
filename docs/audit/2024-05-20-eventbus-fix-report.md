# EventBus 架构审计修复报告

**修复日期:** 2024-05-20  
**修复人员:** Development Team  
**关联审计:** [2024-05-20-eventbus-audit.md](./2024-05-20-eventbus-audit.md)  
**状态:** ✅ 已完成

---

## 修复摘要

| 问题编号 | 严重程度 | 问题描述 | 修复状态 |
|---------|---------|---------|---------|
| 1.1 | 🔴 Critical | 时间确定性违规 | ✅ 已修复 |
| 2.1 | 🟡 Optimization | 事件历史性能 | ✅ 已修复 |
| 2.2 | 🟡 Documentation | 回放限制歧义 | ✅ 已修复 |

---

## 详细修复内容

### 🔴 1.1 时间确定性修复

**问题:** `publish()` 方法硬编码 `timestamp=datetime.now()`，导致回测不确定性。

**修复方案:**

```python
# Before (有问题的代码)
def publish(self, event_type: EventType, data: Any, source: str) -> int:
    event = Event(
        timestamp=datetime.now(),  # 使用墙钟时间
        ...
    )

# After (修复后的代码)
def publish(
    self,
    event_type: EventType,
    data: Any,
    source: str,
    timestamp: Optional[datetime] = None,  # 新增可选参数
) -> int:
    event_timestamp = timestamp if timestamp is not None else datetime.now()
    event = Event(
        timestamp=event_timestamp,  # 使用注入的模拟时间或默认墙钟时间
        ...
    )
```

**使用示例:**

```python
# 回测模式 - 注入模拟时间
sim_time = datetime(2024, 1, 15, 10, 30, 0)
bus.publish(EventType.TICK, {"price": 100}, "backtest_engine", timestamp=sim_time)

# 实盘模式 - 使用默认墙钟时间
bus.publish(EventType.TICK, {"price": 100}, "live_engine")
```

**新增测试:**
- `test_timestamp_injection_for_backtesting` - 验证时间戳注入
- `test_timestamp_defaults_to_now_when_not_provided` - 验证默认行为

---

### 🟡 2.1 事件历史性能优化

**问题:** 使用 list slicing 管理历史大小是 O(N) 操作。

**修复方案:**

```python
# Before (O(N) 操作)
self._event_history: list[Event] = []
# ...
if len(self._event_history) > self._max_history_size:
    self._event_history = self._event_history[-self._max_history_size:]

# After (O(1) 操作)
from collections import deque
self._event_history: deque[Event] = deque(maxlen=max_history_size)
# deque 自动在 C 层处理淘汰，无需手动切片
```

**性能对比:**

| 操作 | list + slicing | deque(maxlen) |
|-----|---------------|---------------|
| 添加元素 | O(1) | O(1) |
| 淘汰旧元素 | O(N) | O(1) |
| 内存分配 | 每次切片重新分配 | 固定大小循环缓冲 |

---

### 🟡 2.2 文档澄清

**问题:** 设计文档承诺"100%可重现性"和"崩溃恢复"，但内存缓冲区有限。

**修复方案:** 在代码和文档中明确说明：

```python
"""
Note on Event History:
    The in-memory event history is a "hot buffer" for UI catch-up and short-term
    replay. For full crash recovery from sequence 0, use the Snapshot mechanism
    (Task 9) or implement an EventPersister to Parquet/SQLite.
"""
```

**架构说明:**

```
┌─────────────────────────────────────────────────────────────┐
│                      EventBus                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Hot Buffer (deque, maxlen=10000)                   │    │
│  │  - UI 追赶                                          │    │
│  │  - 短期回放                                         │    │
│  │  - 调试用途                                         │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Full Recovery (Task 9: Snapshot / EventPersister)          │
│  - 完整崩溃恢复                                              │
│  - 从 Sequence 0 重放                                        │
│  - Parquet/SQLite 持久化                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 改动文件清单

| 文件路径 | 改动类型 | 描述 |
|---------|---------|------|
| `core/engine/event_bus.py` | 修改 | 添加 timestamp 参数，切换到 deque |
| `tests/test_event_bus.py` | 修改 | 新增 2 个测试用例 |
| `CHANGELOG.md` | 修改 | 记录修复内容 |

---

## 测试验证

```bash
$ python -m pytest tests/test_event_bus.py -v
========================= test session starts =========================
collected 9 items

tests/test_event_bus.py::TestEventSequenceMonotonicity::test_sequence_numbers_are_strictly_increasing PASSED
tests/test_event_bus.py::TestEventSequenceMonotonicity::test_sequence_monotonicity_under_concurrent_access PASSED
tests/test_event_bus.py::TestEventSequenceMonotonicity::test_sequence_continues_after_history_clear PASSED
tests/test_event_bus.py::TestEventBusBasicFunctionality::test_subscribe_and_receive_events PASSED
tests/test_event_bus.py::TestEventBusBasicFunctionality::test_timestamp_injection_for_backtesting PASSED
tests/test_event_bus.py::TestEventBusBasicFunctionality::test_timestamp_defaults_to_now_when_not_provided PASSED
tests/test_event_bus.py::TestEventBusBasicFunctionality::test_unsubscribe_stops_receiving_events PASSED
tests/test_event_bus.py::TestEventBusBasicFunctionality::test_replay_from_sequence_number PASSED
tests/test_event_bus.py::TestEventBusBasicFunctionality::test_event_history_size_limit PASSED

========================= 9 passed in 0.89s =========================
```

---

## Git 提交记录

```
commit 6604ef7
Author: Development Team
Date:   2024-05-20

    [Audit Fix] EventBus: timestamp injection + deque optimization
    
    - Add optional timestamp parameter to publish() for deterministic backtesting
    - Switch event history from list to collections.deque for O(1) eviction
    - Document hot buffer vs full recovery architecture
    - Add tests for timestamp injection
```
