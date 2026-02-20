"""
Email Service for Enterprise Scheduler System.

Handles all email sending operations with proper error handling
and logging. Uses Django's email backend configuration.
"""

import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('api')


class EmailService:
    """
    Service class for handling email operations.

    All methods are class methods to allow usage without instantiation.
    """

    @classmethod
    def send_password_reset_email(
        cls,
        user: User,
        uid: str,
        token: str,
        request=None
    ) -> bool:
        """
        Send password reset email to user.

        Args:
            user: User requesting password reset
            uid: Base64 encoded user ID
            token: Password reset token
            request: HTTP request (optional, for building absolute URLs)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Build reset URL
            if request:
                protocol = 'https' if request.is_secure() else 'http'
                domain = request.get_host()
            else:
                protocol = 'https'
                domain = getattr(settings, 'FRONTEND_DOMAIN', 'localhost:3000')

            # Frontend reset URL (adjust path as needed for your frontend)
            reset_url = f"{protocol}://{domain}/auth/reset-password?uid={uid}&token={token}"

            # Email context
            context = {
                'user': user,
                'reset_url': reset_url,
                'valid_hours': getattr(settings, 'PASSWORD_RESET_TIMEOUT', 3600) // 3600,
                'site_name': 'Caliente Scheduler',
            }

            # Plain text message (template fallback)
            plain_message = f"""
Hello {user.first_name or user.username},

You have requested to reset your password for Caliente Scheduler.

Please click the link below to reset your password:
{reset_url}

This link will expire in {context['valid_hours']} hour(s).

If you did not request this password reset, please ignore this email.

Best regards,
Caliente Scheduler Team
            """.strip()

            # Send email
            subject = 'Password Reset Request - Caliente Scheduler'
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@caliente.mx')
            recipient_list = [user.email]

            send_mail(
                subject=subject,
                message=plain_message,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False
            )

            logger.info(f"Password reset email sent to: {user.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
            return False

    @classmethod
    def send_welcome_email(
        cls,
        user: User,
        temporary_password: Optional[str] = None
    ) -> bool:
        """
        Send welcome email to newly created user.

        Args:
            user: Newly created user
            temporary_password: Optional temporary password to include

        Returns:
            bool: True if email sent successfully
        """
        try:
            password_info = ""
            if temporary_password:
                password_info = f"""
Your temporary password is: {temporary_password}

Please change your password after your first login for security.
"""

            subject = 'Welcome to Caliente Scheduler'
            message = f"""
Hello {user.first_name or user.username},

Welcome to the Caliente Enterprise Scheduler System!

Your account has been created successfully. You can now log in using your email address: {user.email}
{password_info}
If you have any questions, please contact your system administrator.

Best regards,
Caliente Scheduler Team
            """.strip()

            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@caliente.mx'),
                recipient_list=[user.email],
                fail_silently=False
            )

            logger.info(f"Welcome email sent to: {user.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
            return False

    @classmethod
    def send_swap_request_notification(
        cls,
        recipient: User,
        requester_name: str,
        swap_details: str
    ) -> bool:
        """
        Send notification email for swap request.

        Args:
            recipient: User to notify
            requester_name: Name of the person requesting swap
            swap_details: Details about the swap request

        Returns:
            bool: True if email sent successfully
        """
        try:
            subject = f'Swap Request from {requester_name} - Caliente Scheduler'
            message = f"""
Hello {recipient.first_name or recipient.username},

You have received a new shift swap request from {requester_name}.

Details:
{swap_details}

Please log in to the Caliente Scheduler system to respond to this request.

Best regards,
Caliente Scheduler Team
            """.strip()

            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@caliente.mx'),
                recipient_list=[recipient.email],
                fail_silently=False
            )

            logger.info(f"Swap request notification sent to: {recipient.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send swap notification to {recipient.email}: {str(e)}")
            return False
