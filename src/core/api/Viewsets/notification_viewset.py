import logging
from rest_framework import viewsets
from api.models import Notification
from api.Serializers.notification_serializer import NotificationSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['Notifications'])
class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet estándar para Notifications."""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer