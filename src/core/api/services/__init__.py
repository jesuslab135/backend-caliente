"""
Services package for Enterprise Scheduler System.

Contains business logic services separated from views/viewsets.
"""

from api.services.email_service import EmailService

__all__ = ['EmailService']
