"""
Property-Based Tests for Authentication Module

This module contains property-based tests using Hypothesis to verify
the correctness properties of the authentication implementation.

Properties tested:
    - Property 19: Role-Based Access Control

Validates: Requirements 12.4
"""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Set

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck

from core.auth import (
    AuthenticationError,
    AuthorizationError,
    AuthErrorCodes,
    UserRole,
    Permission,
    User,
    AuthSession,
    ROLE_PERMISSIONS,
    SQLiteUserManager,
    AuthenticationService,
    AccessControlManager,
    PasswordHasher_,
    require_permission,
    require_role,
    get_access_control_manager,
)
from core.data.key_store import SQLiteKeyStore


# Custom strategies for generating test data
@st.composite
def username_strategy(draw):
    """Generate valid usernames."""
    return draw(st.text(
        min_size=3,
        max_size=30,
        alphabet=st.characters(
            whitelist_categories=('L', 'N'),
            whitelist_characters='_-',
            max_codepoint=127
        )
    ))


@st.composite
def password_strategy(draw):
    """Generate valid passwords."""
    return draw(st.text(
        min_size=8,
        max_size=64,
        alphabet=st.characters(
            whitelist_categories=('L', 'N', 'P'),
            blacklist_characters='\x00\n\r\t',
            max_codepoint=127
        )
    ))


@st.composite
def user_data_strategy(draw):
    """Generate user data for testing."""
    return {
        "username": draw(username_strategy()),
        "password": draw(password_strategy()),
        "role": draw(st.sampled_from([UserRole.ADMIN, UserRole.TRADER])),
        "preferred_language": draw(st.sampled_from(["en", "zh_cn", "zh_tw"])),
    }


class TestRoleBasedAccessControl:
    """
    Property 19: Role-Based Access Control
    
    *For any* user with a specific role (Admin/Trader) and any protected function,
    the access control check must correctly permit or deny access based on the
    role's permissions.
    
    **Validates: Requirements 12.4**
    """
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        """Create a temporary directory for each test."""
        self.db_path = tmp_path / "test.db"
        self.key_dir = tmp_path / "config"
        self.key_dir.mkdir()
        self.user_manager = SQLiteUserManager(db_path=str(self.db_path))
        self.access_control = AccessControlManager()
        yield
    
    @given(role=st.sampled_from([UserRole.ADMIN, UserRole.TRADER]))
    @settings(max_examples=100, deadline=5000)
    def test_admin_has_all_permissions(self, role: UserRole) -> None:
        """
        Property: Admin role must have all permissions.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        if role == UserRole.ADMIN:
            admin_perms = ROLE_PERMISSIONS[UserRole.ADMIN]
            all_perms = set(Permission)
            assert admin_perms == all_perms, "Admin should have all permissions"
    
    @given(permission=st.sampled_from(list(Permission)))
    @settings(max_examples=100, deadline=5000)
    def test_permission_check_consistency(self, permission: Permission) -> None:
        """
        Property: For any permission, the access control check must be
        consistent with the role-permission mapping.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        # Create users with different roles
        admin_user = User(
            user_id=str(uuid.uuid4()),
            username="admin_test",
            password_hash="dummy_hash",
            role=UserRole.ADMIN,
            is_active=True
        )
        
        trader_user = User(
            user_id=str(uuid.uuid4()),
            username="trader_test",
            password_hash="dummy_hash",
            role=UserRole.TRADER,
            is_active=True
        )
        
        # Admin should always have the permission
        assert self.access_control.check_permission(admin_user, permission) is True
        
        # Trader should have permission only if it's in ROLE_PERMISSIONS[TRADER]
        expected_trader_access = permission in ROLE_PERMISSIONS[UserRole.TRADER]
        actual_trader_access = self.access_control.check_permission(trader_user, permission)
        assert actual_trader_access == expected_trader_access
    
    @given(
        role=st.sampled_from([UserRole.ADMIN, UserRole.TRADER]),
        permission=st.sampled_from(list(Permission))
    )
    @settings(max_examples=100, deadline=5000)
    def test_require_permission_raises_correctly(
        self,
        role: UserRole,
        permission: Permission
    ) -> None:
        """
        Property: require_permission must raise AuthorizationError if and only if
        the user doesn't have the permission.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        user = User(
            user_id=str(uuid.uuid4()),
            username=f"test_{role.value}",
            password_hash="dummy_hash",
            role=role,
            is_active=True
        )
        
        has_permission = permission in ROLE_PERMISSIONS[role]
        
        if has_permission:
            # Should not raise
            self.access_control.require_permission(user, permission)
        else:
            # Should raise AuthorizationError
            with pytest.raises(AuthorizationError) as exc_info:
                self.access_control.require_permission(user, permission)
            assert exc_info.value.error_code == AuthErrorCodes.ACCESS_DENIED
    
    @given(role=st.sampled_from([UserRole.ADMIN, UserRole.TRADER]))
    @settings(max_examples=100, deadline=5000)
    def test_inactive_user_has_no_permissions(self, role: UserRole) -> None:
        """
        Property: Inactive users must have no permissions regardless of role.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        inactive_user = User(
            user_id=str(uuid.uuid4()),
            username="inactive_test",
            password_hash="dummy_hash",
            role=role,
            is_active=False
        )
        
        # Inactive user should have no permissions
        for permission in Permission:
            assert self.access_control.check_permission(inactive_user, permission) is False
    
    @given(
        role=st.sampled_from([UserRole.ADMIN, UserRole.TRADER]),
        permissions=st.lists(
            st.sampled_from(list(Permission)),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=100, deadline=5000)
    def test_check_permissions_all(
        self,
        role: UserRole,
        permissions: list[Permission]
    ) -> None:
        """
        Property: check_permissions must return True only if user has ALL permissions.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        user = User(
            user_id=str(uuid.uuid4()),
            username=f"test_{role.value}",
            password_hash="dummy_hash",
            role=role,
            is_active=True
        )
        
        perm_set = set(permissions)
        role_perms = ROLE_PERMISSIONS[role]
        
        # User has all permissions if all requested permissions are in role permissions
        expected = perm_set.issubset(role_perms)
        actual = self.access_control.check_permissions(user, perm_set)
        
        assert actual == expected
    
    @given(
        role=st.sampled_from([UserRole.ADMIN, UserRole.TRADER]),
        permissions=st.lists(
            st.sampled_from(list(Permission)),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=100, deadline=5000)
    def test_check_any_permission(
        self,
        role: UserRole,
        permissions: list[Permission]
    ) -> None:
        """
        Property: check_any_permission must return True if user has ANY permission.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        user = User(
            user_id=str(uuid.uuid4()),
            username=f"test_{role.value}",
            password_hash="dummy_hash",
            role=role,
            is_active=True
        )
        
        perm_set = set(permissions)
        role_perms = ROLE_PERMISSIONS[role]
        
        # User has any permission if at least one requested permission is in role permissions
        expected = bool(perm_set & role_perms)
        actual = self.access_control.check_any_permission(user, perm_set)
        
        assert actual == expected
    
    @given(role=st.sampled_from([UserRole.ADMIN, UserRole.TRADER]))
    @settings(max_examples=100, deadline=5000)
    def test_get_user_permissions_matches_role(self, role: UserRole) -> None:
        """
        Property: get_user_permissions must return exactly the permissions
        defined for the user's role.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        user = User(
            user_id=str(uuid.uuid4()),
            username=f"test_{role.value}",
            password_hash="dummy_hash",
            role=role,
            is_active=True
        )
        
        expected_perms = ROLE_PERMISSIONS[role]
        actual_perms = self.access_control.get_user_permissions(user)
        
        assert actual_perms == expected_perms
    
    def test_trader_cannot_manage_users(self) -> None:
        """
        Property: Traders must not have user management permissions.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        trader_perms = ROLE_PERMISSIONS[UserRole.TRADER]
        
        # Trader should not have user management permissions
        assert Permission.CREATE_USER not in trader_perms
        assert Permission.DELETE_USER not in trader_perms
        assert Permission.MODIFY_USER not in trader_perms
    
    def test_trader_has_trading_permissions(self) -> None:
        """
        Property: Traders must have trading-related permissions.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        trader_perms = ROLE_PERMISSIONS[UserRole.TRADER]
        
        # Trader should have trading permissions
        assert Permission.MANUAL_TRADE in trader_perms
        assert Permission.CLOSE_ALL_POSITIONS in trader_perms
        assert Permission.RUN_BACKTEST in trader_perms
        assert Permission.VIEW_BACKTEST in trader_perms
        assert Permission.EXECUTE_STRATEGY in trader_perms


class TestPasswordHashing:
    """Tests for password hashing functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_hasher(self):
        """Set up password hasher."""
        self.hasher = PasswordHasher_()
        yield
    
    @given(password=password_strategy())
    @settings(max_examples=100, deadline=10000)
    def test_password_hash_round_trip(self, password: str) -> None:
        """
        Property: For any password, hashing and verifying must succeed.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        assume(len(password) >= 8)
        
        # Hash the password
        password_hash = self.hasher.hash(password)
        
        # Verify the password
        assert self.hasher.verify(password, password_hash) is True
    
    @given(
        password1=password_strategy(),
        password2=password_strategy()
    )
    @settings(max_examples=100, deadline=10000)
    def test_different_passwords_different_hashes(
        self,
        password1: str,
        password2: str
    ) -> None:
        """
        Property: Different passwords must produce different hashes.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        assume(len(password1) >= 8)
        assume(len(password2) >= 8)
        assume(password1 != password2)
        
        hash1 = self.hasher.hash(password1)
        hash2 = self.hasher.hash(password2)
        
        # Hashes should be different
        assert hash1 != hash2
        
        # Each password should only verify against its own hash
        assert self.hasher.verify(password1, hash1) is True
        assert self.hasher.verify(password2, hash2) is True
        assert self.hasher.verify(password1, hash2) is False
        assert self.hasher.verify(password2, hash1) is False
    
    @given(password=password_strategy())
    @settings(max_examples=50, deadline=10000)
    def test_same_password_different_hashes(self, password: str) -> None:
        """
        Property: Same password hashed twice must produce different hashes
        (due to random salt).
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        assume(len(password) >= 8)
        
        hash1 = self.hasher.hash(password)
        hash2 = self.hasher.hash(password)
        
        # Hashes should be different (different salts)
        assert hash1 != hash2
        
        # But both should verify the same password
        assert self.hasher.verify(password, hash1) is True
        assert self.hasher.verify(password, hash2) is True


class TestUserManagement:
    """Tests for user management functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        """Create a temporary directory for each test."""
        self.db_path = tmp_path / "test.db"
        self.user_manager = SQLiteUserManager(db_path=str(self.db_path))
        yield
    
    @given(user_data=user_data_strategy())
    @settings(
        max_examples=50,
        deadline=10000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_create_and_retrieve_user(self, user_data: dict) -> None:
        """
        Property: Creating a user and retrieving it must return the same data.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        assume(len(user_data["username"]) >= 3)
        assume(len(user_data["password"]) >= 8)
        
        # Make username unique
        unique_username = f"{user_data['username']}_{uuid.uuid4().hex[:8]}"
        
        # Create user
        user = self.user_manager.create_user(
            username=unique_username,
            password=user_data["password"],
            role=user_data["role"],
            preferred_language=user_data["preferred_language"]
        )
        
        # Retrieve user
        retrieved = self.user_manager.get_user(user.user_id)
        
        assert retrieved is not None
        assert retrieved.username == unique_username
        assert retrieved.role == user_data["role"]
        assert retrieved.preferred_language == user_data["preferred_language"]
    
    @given(user_data=user_data_strategy())
    @settings(
        max_examples=50,
        deadline=10000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_authenticate_user(self, user_data: dict) -> None:
        """
        Property: A user can authenticate with correct credentials.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        assume(len(user_data["username"]) >= 3)
        assume(len(user_data["password"]) >= 8)
        
        # Make username unique
        unique_username = f"{user_data['username']}_{uuid.uuid4().hex[:8]}"
        
        # Create user
        self.user_manager.create_user(
            username=unique_username,
            password=user_data["password"],
            role=user_data["role"]
        )
        
        # Authenticate
        session = self.user_manager.authenticate(
            username=unique_username,
            password=user_data["password"]
        )
        
        assert session is not None
        assert session.user.username == unique_username
        assert session.user.role == user_data["role"]
    
    @given(user_data=user_data_strategy())
    @settings(
        max_examples=50,
        deadline=10000,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_wrong_password_fails(self, user_data: dict) -> None:
        """
        Property: Authentication with wrong password must fail.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        assume(len(user_data["username"]) >= 3)
        assume(len(user_data["password"]) >= 8)
        
        # Make username unique
        unique_username = f"{user_data['username']}_{uuid.uuid4().hex[:8]}"
        
        # Create user
        self.user_manager.create_user(
            username=unique_username,
            password=user_data["password"],
            role=user_data["role"]
        )
        
        # Try to authenticate with wrong password
        with pytest.raises(AuthenticationError) as exc_info:
            self.user_manager.authenticate(
                username=unique_username,
                password="wrong_password_12345"
            )
        
        assert exc_info.value.error_code == AuthErrorCodes.INVALID_PASSWORD
    
    def test_duplicate_username_fails(self) -> None:
        """
        Property: Creating a user with duplicate username must fail.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        username = f"test_user_{uuid.uuid4().hex[:8]}"
        
        # Create first user
        self.user_manager.create_user(
            username=username,
            password="password123",
            role=UserRole.TRADER
        )
        
        # Try to create second user with same username
        with pytest.raises(AuthenticationError) as exc_info:
            self.user_manager.create_user(
                username=username,
                password="different_password",
                role=UserRole.ADMIN
            )
        
        assert exc_info.value.error_code == AuthErrorCodes.USER_ALREADY_EXISTS


class TestDecorators:
    """Tests for permission and role decorators."""
    
    def test_require_permission_decorator_allows(self) -> None:
        """
        Property: @require_permission decorator allows access when user has permission.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        admin_user = User(
            user_id=str(uuid.uuid4()),
            username="admin",
            password_hash="dummy",
            role=UserRole.ADMIN,
            is_active=True
        )
        
        @require_permission(Permission.CREATE_USER)
        def create_user_func(user: User) -> str:
            return "success"
        
        result = create_user_func(user=admin_user)
        assert result == "success"
    
    def test_require_permission_decorator_denies(self) -> None:
        """
        Property: @require_permission decorator denies access when user lacks permission.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        trader_user = User(
            user_id=str(uuid.uuid4()),
            username="trader",
            password_hash="dummy",
            role=UserRole.TRADER,
            is_active=True
        )
        
        @require_permission(Permission.CREATE_USER)
        def create_user_func(user: User) -> str:
            return "success"
        
        with pytest.raises(AuthorizationError):
            create_user_func(user=trader_user)
    
    def test_require_role_decorator_allows(self) -> None:
        """
        Property: @require_role decorator allows access when user has role.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        admin_user = User(
            user_id=str(uuid.uuid4()),
            username="admin",
            password_hash="dummy",
            role=UserRole.ADMIN,
            is_active=True
        )
        
        @require_role(UserRole.ADMIN)
        def admin_only_func(user: User) -> str:
            return "admin_success"
        
        result = admin_only_func(user=admin_user)
        assert result == "admin_success"
    
    def test_require_role_decorator_denies(self) -> None:
        """
        Property: @require_role decorator denies access when user has wrong role.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        trader_user = User(
            user_id=str(uuid.uuid4()),
            username="trader",
            password_hash="dummy",
            role=UserRole.TRADER,
            is_active=True
        )
        
        @require_role(UserRole.ADMIN)
        def admin_only_func(user: User) -> str:
            return "admin_success"
        
        with pytest.raises(AuthorizationError) as exc_info:
            admin_only_func(user=trader_user)
        
        assert exc_info.value.required_role == UserRole.ADMIN.value
        assert exc_info.value.user_role == UserRole.TRADER.value


class TestAuthenticationService:
    """Tests for the authentication service."""
    
    @pytest.fixture(autouse=True)
    def setup_temp_dir(self, tmp_path):
        """Create a temporary directory for each test."""
        self.db_path = tmp_path / "test.db"
        self.key_dir = tmp_path / "config"
        self.key_dir.mkdir()
        
        self.user_manager = SQLiteUserManager(db_path=str(self.db_path))
        self.key_store = SQLiteKeyStore(
            db_path=str(self.db_path),
            key_dir=str(self.key_dir)
        )
        self.auth_service = AuthenticationService(
            user_manager=self.user_manager,
            key_store=self.key_store
        )
        yield
    
    def test_login_creates_session(self) -> None:
        """
        Property: Successful login must create a valid session.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        # Create user
        self.user_manager.create_user(
            username="test_user",
            password="password123",
            role=UserRole.TRADER
        )
        
        # Login
        session, keys = self.auth_service.login(
            username="test_user",
            password="password123",
            ip_address="127.0.0.1"
        )
        
        assert session is not None
        assert session.user.username == "test_user"
        assert session.ip_address == "127.0.0.1"
        assert not session.is_expired()
    
    def test_logout_removes_session(self) -> None:
        """
        Property: Logout must remove the session.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        # Create user and login
        self.user_manager.create_user(
            username="test_user",
            password="password123",
            role=UserRole.TRADER
        )
        
        session, _ = self.auth_service.login(
            username="test_user",
            password="password123"
        )
        
        # Verify session exists
        assert self.auth_service.get_session(session.session_id) is not None
        
        # Logout
        result = self.auth_service.logout(session.session_id)
        assert result is True
        
        # Verify session is removed
        assert self.auth_service.get_session(session.session_id) is None
    
    def test_validate_session_raises_for_invalid(self) -> None:
        """
        Property: validate_session must raise for invalid session.
        
        Feature: titan-quant, Property 19: Role-Based Access Control
        """
        with pytest.raises(AuthenticationError) as exc_info:
            self.auth_service.validate_session("invalid_session_id")
        
        assert exc_info.value.error_code == AuthErrorCodes.SESSION_EXPIRED
