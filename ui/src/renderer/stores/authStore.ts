/**
 * Titan-Quant Authentication Store
 * 
 * Manages authentication state using Zustand.
 * 
 * Requirements:
 *   - 12.1: THE UI_Client SHALL 提供本地登录界面
 *   - 12.3: WHEN 用户登录, THEN THE Titan_Quant_System SHALL 验证密码并解密本地 KeyStore
 *   - 12.4: THE Titan_Quant_System SHALL 根据用户角色限制功能访问
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * User role types
 */
export type UserRole = 'admin' | 'trader';

/**
 * User information
 */
export interface User {
  userId: string;
  username: string;
  role: UserRole;
  preferredLanguage: string;
}

/**
 * Authentication session
 */
export interface AuthSession {
  sessionId: string;
  user: User;
  createdAt: number;
  expiresAt?: number;
}

/**
 * Authentication state
 */
export interface AuthState {
  /** Whether the user is authenticated */
  isAuthenticated: boolean;
  /** Current session information */
  session: AuthSession | null;
  /** Current user information */
  user: User | null;
  /** Whether authentication is in progress */
  isLoading: boolean;
  /** Last authentication error */
  error: string | null;
}

/**
 * Authentication actions
 */
export interface AuthActions {
  /** Set authentication state after successful login */
  login: (session: AuthSession) => void;
  /** Clear authentication state on logout */
  logout: () => void;
  /** Set loading state */
  setLoading: (loading: boolean) => void;
  /** Set error state */
  setError: (error: string | null) => void;
  /** Check if user has a specific permission */
  hasPermission: (permission: string) => boolean;
  /** Check if user has admin role */
  isAdmin: () => boolean;
  /** Update user preferences */
  updateUserPreferences: (preferences: Partial<User>) => void;
}

/**
 * Permission definitions by role
 */
const ROLE_PERMISSIONS: Record<UserRole, Set<string>> = {
  admin: new Set([
    // User management
    'create_user',
    'delete_user',
    'modify_user',
    'view_users',
    // Strategy management
    'create_strategy',
    'delete_strategy',
    'modify_strategy',
    'view_strategy',
    'execute_strategy',
    // Backtest operations
    'run_backtest',
    'view_backtest',
    'delete_backtest',
    // Data management
    'import_data',
    'delete_data',
    'view_data',
    // API key management
    'manage_api_keys',
    'view_api_keys',
    // System configuration
    'modify_system_config',
    'view_system_config',
    // Risk control
    'modify_risk_config',
    'view_risk_config',
    // Manual trading
    'manual_trade',
    'close_all_positions',
    // Reports
    'view_reports',
    'export_reports',
  ]),
  trader: new Set([
    // Strategy permissions
    'create_strategy',
    'modify_strategy',
    'view_strategy',
    'execute_strategy',
    // Backtest permissions
    'run_backtest',
    'view_backtest',
    // Data permissions
    'import_data',
    'view_data',
    // API key permissions (own keys only)
    'manage_api_keys',
    'view_api_keys',
    // View configs
    'view_system_config',
    'view_risk_config',
    // Trading permissions
    'manual_trade',
    'close_all_positions',
    // Reports
    'view_reports',
    'export_reports',
  ]),
};

/**
 * Initial state
 */
const initialState: AuthState = {
  isAuthenticated: false,
  session: null,
  user: null,
  isLoading: false,
  error: null,
};

/**
 * Authentication store
 */
export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set, get) => ({
      ...initialState,

      login: (session: AuthSession) => {
        set({
          isAuthenticated: true,
          session,
          user: session.user,
          isLoading: false,
          error: null,
        });
      },

      logout: () => {
        set({
          ...initialState,
        });
      },

      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },

      setError: (error: string | null) => {
        set({ error, isLoading: false });
      },

      hasPermission: (permission: string): boolean => {
        const { user } = get();
        if (!user) return false;
        
        const permissions = ROLE_PERMISSIONS[user.role];
        return permissions?.has(permission) ?? false;
      },

      isAdmin: (): boolean => {
        const { user } = get();
        return user?.role === 'admin';
      },

      updateUserPreferences: (preferences: Partial<User>) => {
        const { user, session } = get();
        if (!user || !session) return;

        const updatedUser = { ...user, ...preferences };
        set({
          user: updatedUser,
          session: { ...session, user: updatedUser },
        });
      },
    }),
    {
      name: 'titan-quant-auth',
      partialize: (state) => ({
        // Only persist session and user, not loading/error states
        isAuthenticated: state.isAuthenticated,
        session: state.session,
        user: state.user,
      }),
    }
  )
);

/**
 * Hook to check if user is authenticated
 */
export const useIsAuthenticated = () => useAuthStore((state) => state.isAuthenticated);

/**
 * Hook to get current user
 */
export const useCurrentUser = () => useAuthStore((state) => state.user);

/**
 * Hook to check permission
 */
export const useHasPermission = (permission: string) => {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  return hasPermission(permission);
};

/**
 * Hook to check if user is admin
 */
export const useIsAdmin = () => {
  const isAdmin = useAuthStore((state) => state.isAdmin);
  return isAdmin();
};

export default useAuthStore;
