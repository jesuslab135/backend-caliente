"""
URL configuration for Authentication endpoints.

This module defines all auth-related URLs separately from the
main router to maintain the /api/auth/ prefix and custom paths.

Endpoints:
- POST /api/auth/login/              - User login
- POST /api/auth/register/           - Register new user (Admin only)
- POST /api/auth/logout/             - User logout
- POST /api/auth/token/refresh/      - Refresh access token
- POST /api/auth/password-reset/     - Request password reset
- POST /api/auth/password-reset/confirm/ - Confirm password reset
- PUT  /api/auth/password-change/    - Change password
- GET  /api/auth/me/                 - Get current user profile
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.utils import extend_schema

from api.Viewsets.auth_viewset import AuthViewSet


# Extend schema for the SimpleJWT refresh view for better documentation
TokenRefreshViewWithSchema = extend_schema(
    summary="Refresh Access Token",
    description="Get a new access token using a valid refresh token. "
                "The refresh token will be rotated and the old one blacklisted.",
    tags=["Authentication"],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'access': {'type': 'string', 'description': 'New JWT access token'},
                'refresh': {'type': 'string', 'description': 'New JWT refresh token'},
            }
        },
        401: {'description': 'Token is invalid or expired'},
    }
)(TokenRefreshView)


# Create action views from AuthViewSet
login_view = AuthViewSet.as_view({'post': 'login'})
register_view = AuthViewSet.as_view({'post': 'register'})
logout_view = AuthViewSet.as_view({'post': 'logout'})
me_view = AuthViewSet.as_view({'get': 'me'})
password_change_view = AuthViewSet.as_view({'put': 'password_change'})
password_reset_view = AuthViewSet.as_view({'post': 'password_reset'})
password_reset_confirm_view = AuthViewSet.as_view({'post': 'password_reset_confirm'})


urlpatterns = [
    # RF-AUTH-001: Login
    path('login/', login_view, name='auth-login'),

    # Admin-only: Register new user
    path('register/', register_view, name='auth-register'),

    # RF-AUTH-002: Logout (requires blacklist)
    path('logout/', logout_view, name='auth-logout'),

    # RF-AUTH-003: Token Refresh (using SimpleJWT view directly with schema)
    path('token/refresh/', TokenRefreshViewWithSchema.as_view(), name='auth-token-refresh'),

    # RF-AUTH-004: Password Reset
    path('password-reset/', password_reset_view, name='auth-password-reset'),
    path('password-reset/confirm/', password_reset_confirm_view, name='auth-password-reset-confirm'),

    # RF-AUTH-005: Password Change
    path('password-change/', password_change_view, name='auth-password-change'),

    # RF-AUTH-006: Get Current User
    path('me/', me_view, name='auth-me'),
]
