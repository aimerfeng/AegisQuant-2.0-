/**
 * Titan-Quant Login Component Tests
 * 
 * Tests for the Login component functionality.
 * Uses Jest with basic React testing.
 */

import React from 'react';
import { LoginCredentials, LoginResult, LoginProps } from '../components/Login';
import { useAuthStore, AuthSession, User } from '../stores/authStore';

// Test the auth store functionality
describe('Auth Store', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      isAuthenticated: false,
      session: null,
      user: null,
      isLoading: false,
      error: null,
    });
  });

  it('should have initial state', () => {
    const state = useAuthStore.getState();
    
    expect(state.isAuthenticated).toBe(false);
    expect(state.session).toBeNull();
    expect(state.user).toBeNull();
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('should login successfully', () => {
    const mockUser: User = {
      userId: 'test-user-id',
      username: 'testuser',
      role: 'trader',
      preferredLanguage: 'en',
    };

    const mockSession: AuthSession = {
      sessionId: 'test-session-id',
      user: mockUser,
      createdAt: Date.now(),
    };

    useAuthStore.getState().login(mockSession);

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.session).toEqual(mockSession);
    expect(state.user).toEqual(mockUser);
    expect(state.error).toBeNull();
  });

  it('should logout successfully', () => {
    // First login
    const mockUser: User = {
      userId: 'test-user-id',
      username: 'testuser',
      role: 'trader',
      preferredLanguage: 'en',
    };

    const mockSession: AuthSession = {
      sessionId: 'test-session-id',
      user: mockUser,
      createdAt: Date.now(),
    };

    useAuthStore.getState().login(mockSession);
    
    // Then logout
    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.session).toBeNull();
    expect(state.user).toBeNull();
  });

  it('should set loading state', () => {
    useAuthStore.getState().setLoading(true);
    expect(useAuthStore.getState().isLoading).toBe(true);

    useAuthStore.getState().setLoading(false);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it('should set error state', () => {
    const errorMessage = 'Test error message';
    useAuthStore.getState().setError(errorMessage);

    const state = useAuthStore.getState();
    expect(state.error).toBe(errorMessage);
    expect(state.isLoading).toBe(false);
  });

  it('should clear error when set to null', () => {
    useAuthStore.getState().setError('Some error');
    useAuthStore.getState().setError(null);

    expect(useAuthStore.getState().error).toBeNull();
  });

  describe('Permission checks', () => {
    it('should return false for permissions when not logged in', () => {
      const hasPermission = useAuthStore.getState().hasPermission('view_strategy');
      expect(hasPermission).toBe(false);
    });

    it('should check trader permissions correctly', () => {
      const mockUser: User = {
        userId: 'test-user-id',
        username: 'testuser',
        role: 'trader',
        preferredLanguage: 'en',
      };

      const mockSession: AuthSession = {
        sessionId: 'test-session-id',
        user: mockUser,
        createdAt: Date.now(),
      };

      useAuthStore.getState().login(mockSession);

      // Trader should have these permissions
      expect(useAuthStore.getState().hasPermission('view_strategy')).toBe(true);
      expect(useAuthStore.getState().hasPermission('run_backtest')).toBe(true);
      expect(useAuthStore.getState().hasPermission('manual_trade')).toBe(true);

      // Trader should NOT have these permissions
      expect(useAuthStore.getState().hasPermission('create_user')).toBe(false);
      expect(useAuthStore.getState().hasPermission('delete_user')).toBe(false);
      expect(useAuthStore.getState().hasPermission('modify_system_config')).toBe(false);
    });

    it('should check admin permissions correctly', () => {
      const mockUser: User = {
        userId: 'admin-user-id',
        username: 'admin',
        role: 'admin',
        preferredLanguage: 'en',
      };

      const mockSession: AuthSession = {
        sessionId: 'admin-session-id',
        user: mockUser,
        createdAt: Date.now(),
      };

      useAuthStore.getState().login(mockSession);

      // Admin should have all permissions
      expect(useAuthStore.getState().hasPermission('view_strategy')).toBe(true);
      expect(useAuthStore.getState().hasPermission('create_user')).toBe(true);
      expect(useAuthStore.getState().hasPermission('delete_user')).toBe(true);
      expect(useAuthStore.getState().hasPermission('modify_system_config')).toBe(true);
      expect(useAuthStore.getState().hasPermission('modify_risk_config')).toBe(true);
    });
  });

  describe('isAdmin check', () => {
    it('should return false when not logged in', () => {
      expect(useAuthStore.getState().isAdmin()).toBe(false);
    });

    it('should return false for trader role', () => {
      const mockUser: User = {
        userId: 'test-user-id',
        username: 'testuser',
        role: 'trader',
        preferredLanguage: 'en',
      };

      const mockSession: AuthSession = {
        sessionId: 'test-session-id',
        user: mockUser,
        createdAt: Date.now(),
      };

      useAuthStore.getState().login(mockSession);
      expect(useAuthStore.getState().isAdmin()).toBe(false);
    });

    it('should return true for admin role', () => {
      const mockUser: User = {
        userId: 'admin-user-id',
        username: 'admin',
        role: 'admin',
        preferredLanguage: 'en',
      };

      const mockSession: AuthSession = {
        sessionId: 'admin-session-id',
        user: mockUser,
        createdAt: Date.now(),
      };

      useAuthStore.getState().login(mockSession);
      expect(useAuthStore.getState().isAdmin()).toBe(true);
    });
  });

  describe('User preferences update', () => {
    it('should update user preferences', () => {
      const mockUser: User = {
        userId: 'test-user-id',
        username: 'testuser',
        role: 'trader',
        preferredLanguage: 'en',
      };

      const mockSession: AuthSession = {
        sessionId: 'test-session-id',
        user: mockUser,
        createdAt: Date.now(),
      };

      useAuthStore.getState().login(mockSession);
      useAuthStore.getState().updateUserPreferences({ preferredLanguage: 'zh_cn' });

      const state = useAuthStore.getState();
      expect(state.user?.preferredLanguage).toBe('zh_cn');
      expect(state.session?.user.preferredLanguage).toBe('zh_cn');
    });

    it('should not update preferences when not logged in', () => {
      useAuthStore.getState().updateUserPreferences({ preferredLanguage: 'zh_cn' });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
    });
  });
});

// Test Login types
describe('Login Types', () => {
  it('should have correct LoginCredentials structure', () => {
    const credentials: LoginCredentials = {
      username: 'testuser',
      password: 'testpass',
    };

    expect(credentials.username).toBe('testuser');
    expect(credentials.password).toBe('testpass');
  });

  it('should have correct LoginResult structure for success', () => {
    const result: LoginResult = {
      success: true,
      sessionId: 'session-123',
      userId: 'user-123',
      username: 'testuser',
      role: 'trader',
      preferredLanguage: 'en',
    };

    expect(result.success).toBe(true);
    expect(result.sessionId).toBe('session-123');
    expect(result.role).toBe('trader');
  });

  it('should have correct LoginResult structure for failure', () => {
    const result: LoginResult = {
      success: false,
      error: 'Invalid credentials',
      errorCode: 'E8002',
    };

    expect(result.success).toBe(false);
    expect(result.error).toBe('Invalid credentials');
    expect(result.errorCode).toBe('E8002');
  });
});
