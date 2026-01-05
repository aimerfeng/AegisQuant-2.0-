# Titan-Quant Architecture Audit: Tasks 1 & 2

**Reviewer:** Principal Quantitative Engineer  
**Date:** 2024-05-20  
**Status:** ⚠️ Conditional Pass (Critical Fixes Required)

---

## 1. Critical Engineering Flaws (Must Fix)

### 🔴 1.1 Time Determinism Violation in EventBus

**Severity:** Critical  
**Location:** `core/engine/event_bus.py` -> `EventBus.publish`

**Issue:**
The publish method hardcodes `timestamp=datetime.now()`.

```python
event = Event(
    ...,
    timestamp=datetime.now(),  # <--- FATAL FLAW FOR BACKTESTING
    ...
)
```

**Impact:**
This makes the system non-deterministic. In a backtest, the event timestamp MUST reflect the simulation time (e.g., the timestamp of the Tick or Bar being processed), not the wall-clock time of the machine running the code. If you run a backtest on Monday and again on Tuesday, all your timestamp fields will change, breaking any time-based strategy logic (e.g., "close position at 15:00").

**Fix:**
The publish method must accept an optional timestamp argument. The Engine/ReplayController will inject the simulation time.

---

## 2. Optimization Opportunities

### 🟡 2.1 Event History Performance

**Location:** `core/engine/event_bus.py` -> `EventBus.publish`

**Issue:**
Using list slicing for size management is O(N) (copying the list).

```python
self._event_history = self._event_history[-self._max_history_size:]
```

**Impact:**
As the backtest runs, this creates unnecessary memory pressure and CPU cycles.

**Recommendation:**
Use `collections.deque` with `maxlen`. It handles eviction in O(1) time at the C level.

### 🟡 2.2 Replay Limit Ambiguity

**Location:** `core/engine/event_bus.py`

**Issue:**
The `max_history_size` defaults to 10,000.

**Impact:**
The Design Document promises "100% Reproducibility" and "Crash Recovery". If a strategy crashes after 50,000 events, the in-memory buffer cannot replay from the start (Sequence 0).

**Recommendation:**
Explicitly document that EventBus memory history is a hot buffer for UI catch-up. Full crash recovery requires a separate EventPersister (Parquet/SQLite) or Snapshot mechanism (Task 9).

---

## 3. Code Quality & Security

### ✅ 3.1 Exception Hierarchy

**Location:** `core/exceptions.py`  
**Status:** Excellent.

The hierarchy allows for granular error handling. Using string-based ErrorCodes is good for API integration with the frontend.

### ✅ 3.2 Thread Safety

**Location:** `core/engine/event_bus.py`  
**Status:** Good.

Calling handlers outside the lock avoids deadlocks.

```python
with self._lock:
    # ... logic ...
# Call handlers outside
```

---

## 4. Action Plan

1. Refactor EventBus to accept external timestamps.
2. Switch EventBus storage to `collections.deque`.
3. Update Tests to verify timestamp injection.
