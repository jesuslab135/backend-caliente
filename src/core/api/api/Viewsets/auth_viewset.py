"""
Authentication ViewSet for Enterprise Scheduler System.

Implements all authentication endpoints as @action decorators on a single ViewSet:
- RF-AUTH-001: POST /api/auth/login/
- RF-AUTH-002: POST /api/auth/logout/
- RF-AUTH-003: POST /api/auth/token/refresh/ (uses SimpleJWT view)
- RF-AUTH-004: POST /api/auth/password-reset/
- RF-AUTH-005: PUT /api/auth/password-change/
- RF-AUTH-006: GET /api/auth/me/
- Admin-only: POST /api/auth/register/
"""

import logging

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiExample,
)

from api.Serializers.auth_serializers import (
    LoginSerializer,
    LoginResponseSerializer,
    LogoutSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    PasswordChangeSerializer,
    UserProfileSerializer,
    RegisterSerializer,
    RegisterResponseSerializer,
    MessageResponseSerializer,
    ErrorResponseSerializer,
)
from api.services.email_service import EmailService

logger = logging.getLogger('api')


@extend_schema_view(
    login=extend_schema(
        summary="User Login",
        description="Authenticate user with email and password. Returns JWT token pair and user profile.",
        tags=["Authentication"],
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                response=LoginResponseSerializer,
                description="Login successful",
                examples=[
                    OpenApiExample(
                        name="Success Response",
                        value={
                            "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                            "user": {
                                "id": 1,
                                "email": "trader@caliente.mx",
                                "employee_profile": {
                                    "uuid": "550e8400-e29b-41d4-a716-446655440000",
                                    "employee_id": "EMP-001",
                                    "role": "MONITOR_TRADER"
                                }
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Invalid credentials or validation error"
            ),
        }
    ),
    register=extend_schema(
        summary="Register New User (Admin Only)",
        description="Create a new user with employee profile. Requires admin privileges.",
        tags=["Authentication"],
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                response=RegisterResponseSerializer,
                description="User created successfully"
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Validation error"
            ),
            403: OpenApiResponse(
                description="Permission denied - admin access required"
            ),
        }
    ),
    logout=extend_schema(
        summary="User Logout",
        description="Invalidate refresh token by adding it to the blacklist.",
        tags=["Authentication"],
        request=LogoutSerializer,
        responses={
            200: OpenApiResponse(
                response=MessageResponseSerializer,
                description="Logout successful"
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Invalid or expired token"
            ),
        }
    ),
    me=extend_schema(
        summary="Get Current User Profile",
        description="Returns the authenticated user's profile including employee information.",
        tags=["Authentication"],
        responses={
            200: OpenApiResponse(
                response=UserProfileSerializer,
                description="User profile retrieved successfully"
            ),
            401: OpenApiResponse(
                description="Authentication credentials were not provided"
            ),
        }
    ),
    password_change=extend_schema(
        summary="Change Password",
        description="Change the password for the authenticated user. Requires current password.",
        tags=["Authentication"],
        request=PasswordChangeSerializer,
        responses={
            200: OpenApiResponse(
                response=MessageResponseSerializer,
                description="Password changed successfully"
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Validation error"
            ),
        }
    ),
    password_reset=extend_schema(
        summary="Request Password Reset",
        description="Request a password reset email. Always returns success for security.",
        tags=["Authentication"],
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=MessageResponseSerializer,
                description="Reset email sent (if account exists)"
            ),
        }
    ),
    password_reset_confirm=extend_schema(
        summary="Confirm Password Reset",
        description="Set new password using the reset token from email.",
        tags=["Authentication"],
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(
                response=MessageResponseSerializer,
                description="Password reset successfully"
            ),
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Invalid or expired token"
            ),
        }
    ),
)
class AuthViewSet(viewsets.GenericViewSet):
    """
    Authentication ViewSet handling all auth-related operations.

    This ViewSet does not operate on a model queryset - it uses
    custom @action decorators for each authentication operation.
    """

    # No default queryset or serializer_class since we use different
    # serializers per action
    queryset = User.objects.none()

    def get_permissions(self):
        """
        Override to set permissions per action.
        - Public: login, password_reset, password_reset_confirm
        - Authenticated: logout, me, password_change
        - Admin only: register
        """
        public_actions = ['login', 'password_reset', 'password_reset_confirm']
        admin_actions = ['register']

        if self.action in public_actions:
            return [AllowAny()]
        elif self.action in admin_actions:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        """Return appropriate serializer for each action."""
        serializer_map = {
            'login': LoginSerializer,
            'register': RegisterSerializer,
            'logout': LogoutSerializer,
            'me': UserProfileSerializer,
            'password_change': PasswordChangeSerializer,
            'password_reset': PasswordResetRequestSerializer,
            'password_reset_confirm': PasswordResetConfirmSerializer,
        }
        return serializer_map.get(self.action, LoginSerializer)

    # =========================================================================
    # RF-AUTH-001: Login
    # =========================================================================
    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        """
        Authenticate user and return JWT tokens with profile.

        POST /api/auth/login/
        {
            "email": "user@example.com",
            "password": "password123"
        }
        """
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        tokens = serializer.validated_data['tokens']

        logger.info(f"User logged in: {user.email}")

        return Response({
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': UserProfileSerializer(user).data,
        }, status=status.HTTP_200_OK)

    # =========================================================================
    # Admin-only: Register
    # =========================================================================
    @action(detail=False, methods=['post'], url_path='register')
    def register(self, request):
        """
        Create new user with employee profile (Admin only).

        POST /api/auth/register/
        {
            "email": "newuser@caliente.mx",
            "password": "SecurePass123!",
            "first_name": "John",
            "last_name": "Doe",
            "employee_id": "EMP-002",
            "role": "MONITOR_TRADER",
            "phone": "+521234567890",
            "team_id": 1,
            "hire_date": "2024-01-15",
            "send_welcome_email": true
        }
        """
        serializer = RegisterSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        logger.info(f"New user registered by admin {request.user.email}: {result['user'].email}")

        return Response({
            'user': UserProfileSerializer(result['user']).data,
            'message': _('User created successfully.'),
        }, status=status.HTTP_201_CREATED)

    # =========================================================================
    # RF-AUTH-002: Logout
    # =========================================================================
    @action(detail=False, methods=['post'], url_path='logout')
    def logout(self, request):
        """
        Logout user by blacklisting their refresh token.

        POST /api/auth/logout/
        {
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
        }
        """
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"User logged out: {request.user.email}")

        return Response(
            {'message': _('Successfully logged out.'), 'success': True},
            status=status.HTTP_200_OK
        )

    # =========================================================================
    # RF-AUTH-006: Get Current User (Me)
    # =========================================================================
    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        """
        Get current authenticated user's profile with employee data.

        GET /api/auth/me/
        """
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # =========================================================================
    # RF-AUTH-005: Password Change
    # =========================================================================
    @action(detail=False, methods=['put'], url_path='password-change')
    def password_change(self, request):
        """
        Change password for authenticated user.

        PUT /api/auth/password-change/
        {
            "current_password": "oldpassword",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }
        """
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"Password changed for user: {request.user.email}")

        return Response(
            {'message': _('Password changed successfully.'), 'success': True},
            status=status.HTTP_200_OK
        )

    # =========================================================================
    # RF-AUTH-004: Password Reset Request
    # =========================================================================
    @action(detail=False, methods=['post'], url_path='password-reset')
    def password_reset(self, request):
        """
        Request password reset email.
        Always returns success for security (doesn't reveal if email exists).

        POST /api/auth/password-reset/
        {
            "email": "user@example.com"
        }
        """
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.get_user()
        if user:
            # Generate reset token and send email
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Send email via service
            EmailService.send_password_reset_email(
                user=user,
                uid=uid,
                token=token,
                request=request
            )

            logger.info(f"Password reset requested for: {user.email}")
        else:
            logger.warning(f"Password reset for non-existent email: {serializer.validated_data['email']}")

        # Always return success message for security
        return Response(
            {
                'message': _('If an account exists with this email, a password reset link has been sent.'),
                'success': True
            },
            status=status.HTTP_200_OK
        )

    # =========================================================================
    # RF-AUTH-004: Password Reset Confirm
    # =========================================================================
    @action(detail=False, methods=['post'], url_path='password-reset/confirm')
    def password_reset_confirm(self, request):
        """
        Confirm password reset with new password.

        POST /api/auth/password-reset/confirm/
        {
            "uid": "MQ",
            "token": "abc123-token",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        logger.info(f"Password reset completed for: {user.email}")

        return Response(
            {'message': _('Password has been reset successfully.'), 'success': True},
            status=status.HTTP_200_OK
        )
