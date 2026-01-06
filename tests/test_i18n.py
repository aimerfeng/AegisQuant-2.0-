"""
Tests for the I18N (Internationalization) Module

Tests the I18nManager class and related functionality including:
- Language pack loading
- Language switching
- Translation with parameter interpolation
- Fallback language support
- Integration helpers
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from utils.i18n import (
    Language,
    I18nConfig,
    I18nManager,
    I18nKeys,
    get_i18n_manager,
    set_i18n_manager,
    reset_i18n_manager,
    translate,
    set_language,
    get_current_language,
    translate_error,
    translate_audit,
    translate_alert,
    translate_status,
    translate_ui,
    get_localized_action_type,
    get_localized_alert_event,
)


@pytest.fixture
def temp_i18n_dir():
    """Create a temporary directory with test language packs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create English language pack
        en_pack = {
            "error": {
                "insufficient_fund": "Insufficient funds: required {required}, available {available}",
                "order_rejected": "Order rejected: {reason}",
            },
            "audit": {
                "manual_trade": "Manual Trade",
                "param_change": "Parameter Change",
            },
            "alert": {
                "risk_trigger": "Risk Control Triggered: {reason}",
                "backtest_complete": "Backtest Completed",
            },
            "status": {
                "running": "Running",
                "paused": "Paused",
            },
            "ui": {
                "login": "Login",
                "logout": "Logout",
            },
        }
        
        # Create Chinese language pack
        zh_cn_pack = {
            "error": {
                "insufficient_fund": "资金不足：需要 {required}，可用 {available}",
                "order_rejected": "订单被拒绝：{reason}",
            },
            "audit": {
                "manual_trade": "手动交易",
                "param_change": "参数修改",
            },
            "alert": {
                "risk_trigger": "风控触发：{reason}",
                "backtest_complete": "回测完成",
            },
            "status": {
                "running": "运行中",
                "paused": "已暂停",
            },
            "ui": {
                "login": "登录",
                "logout": "登出",
            },
        }
        
        # Write language packs
        with open(os.path.join(tmpdir, "en.json"), "w", encoding="utf-8") as f:
            json.dump(en_pack, f, ensure_ascii=False)
        
        with open(os.path.join(tmpdir, "zh_cn.json"), "w", encoding="utf-8") as f:
            json.dump(zh_cn_pack, f, ensure_ascii=False)
        
        yield tmpdir


@pytest.fixture
def i18n_manager(temp_i18n_dir):
    """Create an I18nManager with test language packs."""
    config = I18nConfig(
        default_language=Language.EN,
        fallback_language=Language.EN,
        language_pack_dir=temp_i18n_dir,
    )
    return I18nManager(config)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before and after each test."""
    reset_i18n_manager()
    yield
    reset_i18n_manager()


class TestI18nManager:
    """Tests for I18nManager class."""
    
    def test_load_language_pack(self, i18n_manager):
        """Test loading a language pack."""
        assert i18n_manager.load_language_pack(Language.EN)
        assert Language.EN in i18n_manager.get_available_languages()
    
    def test_load_nonexistent_language_pack(self, i18n_manager):
        """Test loading a non-existent language pack returns False."""
        assert not i18n_manager.load_language_pack(Language.JA)
    
    def test_set_language(self, i18n_manager):
        """Test setting the current language."""
        assert i18n_manager.set_language(Language.ZH_CN)
        assert i18n_manager.get_current_language() == Language.ZH_CN
    
    def test_set_nonexistent_language(self, i18n_manager):
        """Test setting a non-existent language returns False."""
        assert not i18n_manager.set_language(Language.JA)
    
    def test_translate_simple(self, i18n_manager):
        """Test simple translation without parameters."""
        i18n_manager.set_language(Language.EN)
        assert i18n_manager.translate("audit.manual_trade") == "Manual Trade"
    
    def test_translate_with_parameters(self, i18n_manager):
        """Test translation with parameter interpolation."""
        i18n_manager.set_language(Language.EN)
        result = i18n_manager.translate(
            "error.insufficient_fund",
            required=100,
            available=50
        )
        assert result == "Insufficient funds: required 100, available 50"
    
    def test_translate_chinese(self, i18n_manager):
        """Test translation in Chinese."""
        i18n_manager.set_language(Language.ZH_CN)
        assert i18n_manager.translate("audit.manual_trade") == "手动交易"
    
    def test_translate_chinese_with_parameters(self, i18n_manager):
        """Test Chinese translation with parameter interpolation."""
        i18n_manager.set_language(Language.ZH_CN)
        result = i18n_manager.translate(
            "error.insufficient_fund",
            required=100,
            available=50
        )
        assert result == "资金不足：需要 100，可用 50"
    
    def test_translate_missing_key_returns_key(self, i18n_manager):
        """Test that missing keys return the key itself."""
        result = i18n_manager.translate("nonexistent.key")
        assert result == "nonexistent.key"
    
    def test_fallback_language(self, temp_i18n_dir):
        """Test fallback to default language when key is missing."""
        # Create a partial Chinese pack (missing some keys)
        partial_zh = {
            "error": {
                "insufficient_fund": "资金不足",
            }
        }
        with open(os.path.join(temp_i18n_dir, "zh_cn.json"), "w", encoding="utf-8") as f:
            json.dump(partial_zh, f)
        
        config = I18nConfig(
            default_language=Language.ZH_CN,
            fallback_language=Language.EN,
            language_pack_dir=temp_i18n_dir,
        )
        manager = I18nManager(config)
        
        # This key exists in Chinese
        assert manager.translate("error.insufficient_fund") == "资金不足"
        
        # This key only exists in English (fallback)
        assert manager.translate("audit.manual_trade") == "Manual Trade"
    
    def test_get_all_keys(self, i18n_manager):
        """Test getting all translation keys."""
        keys = i18n_manager.get_all_keys()
        assert "error.insufficient_fund" in keys
        assert "audit.manual_trade" in keys
        assert "alert.risk_trigger" in keys
    
    def test_has_key(self, i18n_manager):
        """Test checking if a key exists."""
        assert i18n_manager.has_key("error.insufficient_fund")
        assert not i18n_manager.has_key("nonexistent.key")
    
    def test_reload_language_packs(self, i18n_manager, temp_i18n_dir):
        """Test reloading language packs."""
        # Modify the English pack
        new_pack = {
            "error": {
                "insufficient_fund": "Not enough money!",
            }
        }
        with open(os.path.join(temp_i18n_dir, "en.json"), "w", encoding="utf-8") as f:
            json.dump(new_pack, f)
        
        # Reload
        i18n_manager.reload_language_packs()
        
        # Check new translation
        assert i18n_manager.translate("error.insufficient_fund") == "Not enough money!"


class TestSingletonFunctions:
    """Tests for singleton convenience functions."""
    
    def test_get_i18n_manager_creates_singleton(self):
        """Test that get_i18n_manager creates a singleton."""
        manager1 = get_i18n_manager()
        manager2 = get_i18n_manager()
        assert manager1 is manager2
    
    def test_set_i18n_manager(self, i18n_manager):
        """Test setting a custom I18nManager."""
        set_i18n_manager(i18n_manager)
        assert get_i18n_manager() is i18n_manager
    
    def test_translate_function(self, i18n_manager):
        """Test the translate convenience function."""
        set_i18n_manager(i18n_manager)
        assert translate("audit.manual_trade") == "Manual Trade"
    
    def test_set_language_function(self, i18n_manager):
        """Test the set_language convenience function."""
        set_i18n_manager(i18n_manager)
        assert set_language(Language.ZH_CN)
        assert get_current_language() == Language.ZH_CN


class TestIntegrationHelpers:
    """Tests for I18N integration helper functions."""
    
    def test_translate_error(self, i18n_manager):
        """Test translate_error helper."""
        set_i18n_manager(i18n_manager)
        result = translate_error("insufficient_fund", required=100, available=50)
        assert "100" in result
        assert "50" in result
    
    def test_translate_error_with_prefix(self, i18n_manager):
        """Test translate_error with full key."""
        set_i18n_manager(i18n_manager)
        result = translate_error("error.insufficient_fund", required=100, available=50)
        assert "100" in result
    
    def test_translate_audit(self, i18n_manager):
        """Test translate_audit helper."""
        set_i18n_manager(i18n_manager)
        assert translate_audit("manual_trade") == "Manual Trade"
    
    def test_translate_alert(self, i18n_manager):
        """Test translate_alert helper."""
        set_i18n_manager(i18n_manager)
        result = translate_alert("risk_trigger", reason="Drawdown exceeded")
        assert "Drawdown exceeded" in result
    
    def test_translate_status(self, i18n_manager):
        """Test translate_status helper."""
        set_i18n_manager(i18n_manager)
        assert translate_status("running") == "Running"
    
    def test_translate_ui(self, i18n_manager):
        """Test translate_ui helper."""
        set_i18n_manager(i18n_manager)
        assert translate_ui("login") == "Login"
    
    def test_get_localized_action_type(self, i18n_manager):
        """Test get_localized_action_type helper."""
        set_i18n_manager(i18n_manager)
        assert get_localized_action_type("MANUAL_TRADE") == "Manual Trade"
        assert get_localized_action_type("PARAM_CHANGE") == "Parameter Change"
    
    def test_get_localized_alert_event(self, i18n_manager):
        """Test get_localized_alert_event helper."""
        set_i18n_manager(i18n_manager)
        result = get_localized_alert_event("backtest_complete")
        assert result == "Backtest Completed"


class TestI18nKeys:
    """Tests for I18nKeys constants."""
    
    def test_error_keys_exist(self):
        """Test that error keys are defined."""
        assert I18nKeys.ERROR_INSUFFICIENT_FUND == "error.insufficient_fund"
        assert I18nKeys.ERROR_ORDER_REJECTED == "error.order_rejected"
    
    def test_audit_keys_exist(self):
        """Test that audit keys are defined."""
        assert I18nKeys.AUDIT_MANUAL_TRADE == "audit.manual_trade"
        assert I18nKeys.AUDIT_PARAM_CHANGE == "audit.param_change"
    
    def test_alert_keys_exist(self):
        """Test that alert keys are defined."""
        assert I18nKeys.ALERT_RISK_TRIGGER == "alert.risk_trigger"
        assert I18nKeys.ALERT_BACKTEST_COMPLETE == "alert.backtest_complete"
    
    def test_status_keys_exist(self):
        """Test that status keys are defined."""
        assert I18nKeys.STATUS_RUNNING == "status.running"
        assert I18nKeys.STATUS_PAUSED == "status.paused"
    
    def test_ui_keys_exist(self):
        """Test that UI keys are defined."""
        assert I18nKeys.UI_LOGIN == "ui.login"
        assert I18nKeys.UI_LOGOUT == "ui.logout"


class TestRealLanguagePacks:
    """Tests using the real language pack files."""
    
    def test_load_real_english_pack(self):
        """Test loading the real English language pack."""
        config = I18nConfig(
            default_language=Language.EN,
            fallback_language=Language.EN,
            language_pack_dir="config/i18n",
        )
        manager = I18nManager(config)
        
        # Check that the pack loaded
        assert Language.EN in manager.get_available_languages()
        
        # Check some translations
        assert "Insufficient" in manager.translate("error.insufficient_fund", required=100, available=50)
    
    def test_load_real_chinese_pack(self):
        """Test loading the real Chinese language pack."""
        config = I18nConfig(
            default_language=Language.ZH_CN,
            fallback_language=Language.EN,
            language_pack_dir="config/i18n",
        )
        manager = I18nManager(config)
        
        # Check that the pack loaded
        assert Language.ZH_CN in manager.get_available_languages()
        
        # Check some translations
        assert "资金不足" in manager.translate("error.insufficient_fund", required=100, available=50)
    
    def test_load_real_traditional_chinese_pack(self):
        """Test loading the real Traditional Chinese language pack."""
        config = I18nConfig(
            default_language=Language.ZH_TW,
            fallback_language=Language.EN,
            language_pack_dir="config/i18n",
        )
        manager = I18nManager(config)
        
        # Check that the pack loaded
        assert Language.ZH_TW in manager.get_available_languages()
        
        # Check some translations
        assert "資金不足" in manager.translate("error.insufficient_fund", required=100, available=50)
