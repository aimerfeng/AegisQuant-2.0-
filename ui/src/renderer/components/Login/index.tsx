/**
 * Titan-Quant Login Component
 * 
 * Provides local login interface for user authentication.
 * 
 * Requirements:
 *   - 12.1: THE UI_Client SHALL 提供本地登录界面
 *   - 12.3: WHEN 用户登录, THEN THE Titan_Quant_System SHALL 验证密码并解密本地 KeyStore
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageType } from '../../types/websocket';
import { getWebSocketService } from '../../services/websocket';
import './Login.css';

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface LoginResult {
  success: boolean;
  sessionId?: string;
  userId?: string;
  username?: string;
  role?: 'admin' | 'trader';
  preferredLanguage?: string;
  error?: string;
  errorCode?: string;
}

export interface LoginProps {
  /** Callback when login is successful */
  onLoginSuccess?: (result: LoginResult) => void;
  /** Callback when login fails */
  onLoginError?: (error: string) => void;
  /** Whether to show the logo */
  showLogo?: boolean;
  /** Custom logo URL */
  logoUrl?: string;
  /** Whether the component is in loading state */
  isLoading?: boolean;
}

/**
 * Login component for user authentication
 */
const Login: React.FC<LoginProps> = ({
  onLoginSuccess,
  onLoginError,
  showLogo = true,
  logoUrl,
  isLoading: externalLoading = false,
}) => {
  const { t } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  // Load remembered username on mount
  useEffect(() => {
    const savedUsername = localStorage.getItem('titan_quant_remembered_username');
    if (savedUsername) {
      setUsername(savedUsername);
      setRememberMe(true);
    }
  }, []);

  /**
   * Handle form submission
   */
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Clear previous error
    setError(null);

    // Validate inputs
    if (!username.trim()) {
      setError(t('login.usernameRequired'));
      return;
    }

    if (!password) {
      setError(t('login.passwordRequired'));
      return;
    }

    setIsLoading(true);

    try {
      // Get WebSocket service
      const wsService = getWebSocketService();

      // Create a promise to handle the login response
      const loginPromise = new Promise<LoginResult>((resolve, reject) => {
        // Set up response handler
        const unsubscribe = wsService.subscribe(MessageType.STATUS, (message) => {
          const payload = message.payload as LoginResult;
          unsubscribe();
          
          if (payload.success) {
            resolve(payload);
          } else {
            reject(new Error(payload.error || t('login.unknownError')));
          }
        });

        // Set up error handler
        const unsubscribeError = wsService.subscribe(MessageType.ERROR, (message) => {
          const payload = message.payload as { message: string; code?: string };
          unsubscribeError();
          reject(new Error(payload.message || t('login.unknownError')));
        });

        // Send login request
        wsService.send(MessageType.CONNECT, {
          action: 'login',
          username: username.trim(),
          password,
        });

        // Timeout after 30 seconds
        setTimeout(() => {
          unsubscribe();
          unsubscribeError();
          reject(new Error(t('login.timeout')));
        }, 30000);
      });

      const result = await loginPromise;

      // Save username if remember me is checked
      if (rememberMe) {
        localStorage.setItem('titan_quant_remembered_username', username.trim());
      } else {
        localStorage.removeItem('titan_quant_remembered_username');
      }

      // Call success callback
      onLoginSuccess?.(result);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('login.unknownError');
      setError(errorMessage);
      onLoginError?.(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [username, password, rememberMe, t, onLoginSuccess, onLoginError]);

  /**
   * Handle username input change
   */
  const handleUsernameChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setUsername(e.target.value);
    if (error) setError(null);
  }, [error]);

  /**
   * Handle password input change
   */
  const handlePasswordChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setPassword(e.target.value);
    if (error) setError(null);
  }, [error]);

  /**
   * Toggle password visibility
   */
  const togglePasswordVisibility = useCallback(() => {
    setShowPassword(prev => !prev);
  }, []);

  /**
   * Handle remember me checkbox change
   */
  const handleRememberMeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setRememberMe(e.target.checked);
  }, []);

  const loading = isLoading || externalLoading;

  return (
    <div className="login-container">
      <div className="login-card">
        {/* Logo Section */}
        {showLogo && (
          <div className="login-logo">
            {logoUrl ? (
              <img src={logoUrl} alt="Titan-Quant" className="login-logo-image" />
            ) : (
              <div className="login-logo-text">
                <span className="login-logo-icon">📊</span>
                <h1>Titan-Quant</h1>
              </div>
            )}
            <p className="login-subtitle">{t('app.subtitle')}</p>
          </div>
        )}

        {/* Login Form */}
        <form className="login-form" onSubmit={handleSubmit}>
          {/* Error Message */}
          {error && (
            <div className="login-error" role="alert">
              <span className="login-error-icon">⚠️</span>
              <span className="login-error-text">{error}</span>
            </div>
          )}

          {/* Username Field */}
          <div className="login-field">
            <label htmlFor="username" className="login-label">
              {t('login.username')}
            </label>
            <div className="login-input-wrapper">
              <span className="login-input-icon">👤</span>
              <input
                id="username"
                type="text"
                className="login-input"
                value={username}
                onChange={handleUsernameChange}
                placeholder={t('login.usernamePlaceholder')}
                disabled={loading}
                autoComplete="username"
                autoFocus
              />
            </div>
          </div>

          {/* Password Field */}
          <div className="login-field">
            <label htmlFor="password" className="login-label">
              {t('login.password')}
            </label>
            <div className="login-input-wrapper">
              <span className="login-input-icon">🔒</span>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                className="login-input"
                value={password}
                onChange={handlePasswordChange}
                placeholder={t('login.passwordPlaceholder')}
                disabled={loading}
                autoComplete="current-password"
              />
              <button
                type="button"
                className="login-password-toggle"
                onClick={togglePasswordVisibility}
                disabled={loading}
                aria-label={showPassword ? t('login.hidePassword') : t('login.showPassword')}
              >
                {showPassword ? '👁️' : '👁️‍🗨️'}
              </button>
            </div>
          </div>

          {/* Remember Me */}
          <div className="login-options">
            <label className="login-remember">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={handleRememberMeChange}
                disabled={loading}
              />
              <span>{t('login.rememberMe')}</span>
            </label>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            className="login-button"
            disabled={loading || !username.trim() || !password}
          >
            {loading ? (
              <>
                <span className="login-spinner"></span>
                <span>{t('login.loggingIn')}</span>
              </>
            ) : (
              <span>{t('ui.login')}</span>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="login-footer">
          <p className="login-version">{t('app.version', { version: '1.0.0' })}</p>
        </div>
      </div>
    </div>
  );
};

export default Login;
