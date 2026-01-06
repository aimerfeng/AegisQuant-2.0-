-- Titan-Quant Database Schema
-- SQLite Database Schema for Titan-Quant Quantitative Trading System
-- Version: 1.0.0

-- ============================================================================
-- 用户表 (Users Table)
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,      -- Argon2 hash
    role TEXT NOT NULL CHECK (role IN ('admin', 'trader')),
    settings TEXT,                     -- UI偏好设置 JSON
    preferred_language TEXT DEFAULT 'zh_cn',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Index for username lookup
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ============================================================================
-- API 密钥表 (Exchange Keys Table) - 加密存储
-- ============================================================================
CREATE TABLE IF NOT EXISTS exchange_keys (
    key_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
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

-- Index for user_id lookup
CREATE INDEX IF NOT EXISTS idx_exchange_keys_user_id ON exchange_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_exchange_keys_exchange ON exchange_keys(exchange);

-- ============================================================================
-- 策略元数据表 (Strategies Table)
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategies (
    strategy_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    class_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    parameters TEXT,                   -- JSON
    checksum TEXT NOT NULL,            -- 文件校验和，防止代码被篡改
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Index for strategy name lookup
CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name);
CREATE INDEX IF NOT EXISTS idx_strategies_class_name ON strategies(class_name);

-- ============================================================================
-- 回测记录表 (Backtest Records Table)
-- ============================================================================
CREATE TABLE IF NOT EXISTS backtest_records (
    backtest_id TEXT PRIMARY KEY,
    strategy_id TEXT REFERENCES strategies(strategy_id) ON DELETE SET NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital REAL NOT NULL,
    matching_mode TEXT NOT NULL,       -- "L1" | "L2"
    l2_level TEXT,                     -- "LEVEL_1" | "LEVEL_2" | "LEVEL_3"
    data_provider TEXT,                -- 数据源名称
    status TEXT NOT NULL CHECK (status IN ('running', 'paused', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Index for strategy_id and status lookup
CREATE INDEX IF NOT EXISTS idx_backtest_records_strategy_id ON backtest_records(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_records_status ON backtest_records(status);
CREATE INDEX IF NOT EXISTS idx_backtest_records_created_at ON backtest_records(created_at);

-- ============================================================================
-- 回测结果表 (Backtest Results Table)
-- ============================================================================
CREATE TABLE IF NOT EXISTS backtest_results (
    result_id TEXT PRIMARY KEY,
    backtest_id TEXT NOT NULL REFERENCES backtest_records(backtest_id) ON DELETE CASCADE,
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

-- Index for backtest_id lookup
CREATE INDEX IF NOT EXISTS idx_backtest_results_backtest_id ON backtest_results(backtest_id);

-- ============================================================================
-- 快照表 (Snapshots Table)
-- ============================================================================
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    backtest_id TEXT REFERENCES backtest_records(backtest_id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    file_path TEXT NOT NULL,
    data_timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for backtest_id lookup
CREATE INDEX IF NOT EXISTS idx_snapshots_backtest_id ON snapshots(backtest_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_data_timestamp ON snapshots(data_timestamp);

-- ============================================================================
-- 告警配置表 (Alert Configs Table)
-- ============================================================================
CREATE TABLE IF NOT EXISTS alert_configs (
    config_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    alert_type TEXT NOT NULL CHECK (alert_type IN ('sync', 'async')),
    channels TEXT NOT NULL,            -- JSON array: ["email", "webhook", "system_notification"]
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Index for event_type lookup
CREATE INDEX IF NOT EXISTS idx_alert_configs_event_type ON alert_configs(event_type);
CREATE INDEX IF NOT EXISTS idx_alert_configs_enabled ON alert_configs(enabled);

-- ============================================================================
-- 数据源配置表 (Data Providers Table)
-- ============================================================================
CREATE TABLE IF NOT EXISTS data_providers (
    provider_id TEXT PRIMARY KEY,
    provider_type TEXT NOT NULL CHECK (provider_type IN ('parquet', 'mysql', 'mongodb', 'dolphindb')),
    name TEXT NOT NULL,
    connection_config TEXT NOT NULL,   -- JSON (加密敏感字段)
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Index for provider_type and is_default lookup
CREATE INDEX IF NOT EXISTS idx_data_providers_type ON data_providers(provider_type);
CREATE INDEX IF NOT EXISTS idx_data_providers_default ON data_providers(is_default);

-- ============================================================================
-- Trigger: 确保只有一个默认数据源
-- ============================================================================
CREATE TRIGGER IF NOT EXISTS ensure_single_default_provider
BEFORE UPDATE ON data_providers
WHEN NEW.is_default = TRUE
BEGIN
    UPDATE data_providers SET is_default = FALSE WHERE provider_id != NEW.provider_id;
END;

CREATE TRIGGER IF NOT EXISTS ensure_single_default_provider_insert
BEFORE INSERT ON data_providers
WHEN NEW.is_default = TRUE
BEGIN
    UPDATE data_providers SET is_default = FALSE;
END;

-- ============================================================================
-- Trigger: 自动更新 updated_at 字段
-- ============================================================================
CREATE TRIGGER IF NOT EXISTS update_exchange_keys_timestamp
AFTER UPDATE ON exchange_keys
BEGIN
    UPDATE exchange_keys SET updated_at = CURRENT_TIMESTAMP WHERE key_id = NEW.key_id;
END;

CREATE TRIGGER IF NOT EXISTS update_strategies_timestamp
AFTER UPDATE ON strategies
BEGIN
    UPDATE strategies SET updated_at = CURRENT_TIMESTAMP WHERE strategy_id = NEW.strategy_id;
END;

CREATE TRIGGER IF NOT EXISTS update_alert_configs_timestamp
AFTER UPDATE ON alert_configs
BEGIN
    UPDATE alert_configs SET updated_at = CURRENT_TIMESTAMP WHERE config_id = NEW.config_id;
END;

CREATE TRIGGER IF NOT EXISTS update_data_providers_timestamp
AFTER UPDATE ON data_providers
BEGIN
    UPDATE data_providers SET updated_at = CURRENT_TIMESTAMP WHERE provider_id = NEW.provider_id;
END;
