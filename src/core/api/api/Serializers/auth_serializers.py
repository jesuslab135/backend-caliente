"""
Authentication Serializers for Enterprise Scheduler System.

Implements serializers for:
- RF-AUTH-001: Login
- RF-AUTH-002: Logout
- RF-AUTH-003: Token Refresh (uses SimpleJWT default)
- RF-AUTH-004: Password Reset
- RF-AUTH-005: Password Change
- RF-AUTH-006: User Profile (Me)
- Admin-only: Register (User + Employee creation)
"""

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import Employee, Team


# =============================================================================
# NESTED SERIALIZERS for /me/ endpoint
# =============================================================================

class TeamNestedSerializer(serializers.ModelSerializer):
    """Lightweight team serializer for nested employee data."""

    class Meta:
        model = Team
        fields = ['uuid', 'name', 'is_active']
        read_only_fields = fields


class EmployeeProfileSerializer(serializers.ModelSerializer):
    """
    Employee profile serializer for /me/ endpoint.
    Includes team information as nested object.
    """
    team = TeamNestedSerializer(read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = Employee
        fields = [
            'uuid',
            'employee_id',
            'phone',
            'role',
            'role_display',
            'team',
            'is_active',
            'hire_date',
            'created_at',
        ]
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    """
    User profile serializer for /me/ endpoint.
    Includes nested employee profile with full information.
    """
    employee_profile = EmployeeProfileSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'is_active',
            'is_staff',
            'date_joined',
            'last_login',
            'employee_profile',
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        """Return full name or username as fallback."""
        return obj.get_full_name() or obj.username


# =============================================================================
# RF-AUTH-001: LOGIN SERIALIZER
# =============================================================================

class LoginSerializer(serializers.Serializer):
    """
    Custom login serializer for JWT authentication.

    Enhancements:
    - Validates user has employee profile
    - Validates employee is_active
    - Returns user profile data with tokens
    - Uses email for authentication
    """
    email = serializers.EmailField(
        required=True,
        help_text=_('User email address')
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text=_('User password')
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError(
                _('Both email and password are required.'),
                code='invalid_credentials'
            )

        # Find user by email
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {'detail': _('Invalid email or password.')},
                code='invalid_credentials'
            )

        # Authenticate
        if not user.check_password(password):
            raise serializers.ValidationError(
                {'detail': _('Invalid email or password.')},
                code='invalid_credentials'
            )

        # Check user is active
        if not user.is_active:
            raise serializers.ValidationError(
                {'detail': _('This account has been deactivated.')},
                code='account_disabled'
            )

        # Check employee profile exists and is active
        try:
            employee = user.employee_profile
            if not employee.is_active:
                raise serializers.ValidationError(
                    {'detail': _('This employee account is inactive.')},
                    code='employee_inactive'
                )
        except Employee.DoesNotExist:
            raise serializers.ValidationError(
                {'detail': _('No employee profile associated with this account.')},
                code='no_employee_profile'
            )

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        # Add custom claims to token
        refresh['email'] = user.email
        refresh['employee_id'] = employee.employee_id
        refresh['role'] = employee.role

        attrs['user'] = user
        attrs['tokens'] = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }

        return attrs


class LoginResponseSerializer(serializers.Serializer):
    """Response serializer for login endpoint (for OpenAPI docs)."""
    access = serializers.CharField(help_text=_('JWT access token'))
    refresh = serializers.CharField(help_text=_('JWT refresh token'))
    user = UserProfileSerializer(help_text=_('User profile with employee data'))


# =============================================================================
# RF-AUTH-002: LOGOUT SERIALIZER
# =============================================================================

class LogoutSerializer(serializers.Serializer):
    """
    Logout serializer - blacklists the refresh token.
    """
    refresh = serializers.CharField(
        required=True,
        help_text=_('Refresh token to invalidate')
    )

    def validate_refresh(self, value):
        """Validate refresh token format."""
        if not value:
            raise serializers.ValidationError(
                _('Refresh token is required.')
            )
        return value

    def save(self, **kwargs):
        """Blacklist the refresh token."""
        try:
            token = RefreshToken(self.validated_data['refresh'])
            token.blacklist()
        except Exception as e:
            raise serializers.ValidationError(
                {'refresh': _('Invalid or expired token.')}
            )


# =============================================================================
# RF-AUTH-004: PASSWORD RESET SERIALIZERS
# =============================================================================

class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Request password reset - sends email with reset link.
    """
    email = serializers.EmailField(
        required=True,
        help_text=_('Email address associated with the account')
    )

    def validate_email(self, value):
        """
        Validate email format but don't reveal if account doesn't exist.
        We return success either way for security.
        """
        # Normalize email
        return value.lower().strip()

    def get_user(self):
        """Get user by email if exists."""
        email = self.validated_data.get('email')
        try:
            return User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            return None


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Confirm password reset with new password.
    """
    uid = serializers.CharField(
        required=True,
        help_text=_('User ID encoded in base64')
    )
    token = serializers.CharField(
        required=True,
        help_text=_('Password reset token')
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text=_('New password (minimum 8 characters)')
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text=_('Confirm new password')
    )

    def validate(self, attrs):
        # Validate passwords match
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': _('Passwords do not match.')}
            )

        # Decode UID and get user
        try:
            uid = urlsafe_base64_decode(attrs['uid']).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError(
                {'uid': _('Invalid reset link.')}
            )

        # Validate token
        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError(
                {'token': _('Invalid or expired reset token.')}
            )

        # Validate password complexity
        try:
            validate_password(attrs['new_password'], user)
        except Exception as e:
            raise serializers.ValidationError(
                {'new_password': list(e.messages)}
            )

        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        """Set the new password."""
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


# =============================================================================
# RF-AUTH-005: PASSWORD CHANGE SERIALIZER
# =============================================================================

class PasswordChangeSerializer(serializers.Serializer):
    """
    Change password for authenticated user.
    Requires current password validation.
    """
    current_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text=_('Current password')
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text=_('New password (minimum 8 characters)')
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text=_('Confirm new password')
    )

    def validate_current_password(self, value):
        """Validate current password is correct."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(
                _('Current password is incorrect.')
            )
        return value

    def validate(self, attrs):
        # Validate passwords match
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': _('Passwords do not match.')}
            )

        # Validate not same as current
        if attrs['new_password'] == attrs['current_password']:
            raise serializers.ValidationError(
                {'new_password': _('New password must be different from current password.')}
            )

        # Validate password complexity
        user = self.context['request'].user
        try:
            validate_password(attrs['new_password'], user)
        except Exception as e:
            raise serializers.ValidationError(
                {'new_password': list(e.messages)}
            )

        return attrs

    def save(self, **kwargs):
        """Set the new password."""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


# =============================================================================
# REGISTER SERIALIZER (Admin-only)
# =============================================================================

class RegisterSerializer(serializers.Serializer):
    """
    Register new user with employee profile (Admin only).

    Creates both User and Employee in a single transaction.
    """
    # User fields
    email = serializers.EmailField(
        required=True,
        help_text=_('User email address (must be unique)')
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text=_('Password (minimum 8 characters)')
    )
    first_name = serializers.CharField(
        required=True,
        max_length=150,
        help_text=_('First name')
    )
    last_name = serializers.CharField(
        required=True,
        max_length=150,
        help_text=_('Last name')
    )

    # Employee fields
    employee_id = serializers.CharField(
        required=True,
        max_length=20,
        help_text=_('Unique employee code (e.g., EMP-001)')
    )
    role = serializers.ChoiceField(
        choices=Employee.Role.choices,
        required=True,
        help_text=_('Employee role')
    )
    phone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=20,
        help_text=_('Phone number for notifications')
    )
    team_id = serializers.SlugRelatedField(
        queryset=Team.objects.all(),
        slug_field='uuid',
        required=False,
        allow_null=True,
        help_text=_('Team UUID (optional)')
    )
    hire_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text=_('Hire date (optional)')
    )

    # Options
    send_welcome_email = serializers.BooleanField(
        required=False,
        default=True,
        help_text=_('Send welcome email with credentials')
    )

    def validate_email(self, value):
        """Validate email is unique."""
        email = value.lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                _('A user with this email already exists.')
            )
        return email

    def validate_employee_id(self, value):
        """Validate employee_id is unique."""
        if Employee.objects.filter(employee_id=value).exists():
            raise serializers.ValidationError(
                _('An employee with this ID already exists.')
            )
        return value

    def validate_password(self, value):
        """Validate password complexity."""
        try:
            validate_password(value)
        except Exception as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        """Additional cross-field validation."""
        # If role is ADMIN or MANAGER, warn about permissions
        # (actual permission setup would be handled separately)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create User and Employee in transaction."""
        # Extract fields
        email = validated_data['email']
        password = validated_data['password']
        first_name = validated_data['first_name']
        last_name = validated_data['last_name']

        employee_id = validated_data['employee_id']
        role = validated_data['role']
        phone = validated_data.get('phone', '')
        team = validated_data.get('team_id')
        hire_date = validated_data.get('hire_date')
        send_welcome = validated_data.get('send_welcome_email', True)

        # Create username from email (before @)
        username = email.split('@')[0]
        # Ensure unique username
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )

        # Set is_staff for ADMIN/MANAGER roles
        if role in [Employee.Role.ADMIN, Employee.Role.MANAGER]:
            user.is_staff = True
            user.save()

        # Create Employee
        employee = Employee.objects.create(
            user=user,
            employee_id=employee_id,
            role=role,
            phone=phone,
            team=team,
            hire_date=hire_date,
            is_active=True,
        )

        # Send welcome email if requested
        if send_welcome:
            from api.services.email_service import EmailService
            EmailService.send_welcome_email(user, temporary_password=password)

        return {
            'user': user,
            'employee': employee,
        }


class RegisterResponseSerializer(serializers.Serializer):
    """Response serializer for register endpoint (for OpenAPI docs)."""
    user = UserProfileSerializer()
    message = serializers.CharField()


# =============================================================================
# GENERIC RESPONSE SERIALIZERS (for OpenAPI documentation)
# =============================================================================

class MessageResponseSerializer(serializers.Serializer):
    """Generic message response."""
    message = serializers.CharField(help_text=_('Response message'))
    success = serializers.BooleanField(default=True)


class ErrorResponseSerializer(serializers.Serializer):
    """Generic error response."""
    detail = serializers.CharField(help_text=_('Error detail message'))
    code = serializers.CharField(required=False, help_text=_('Error code'))
