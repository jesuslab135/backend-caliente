import logging
from rest_framework import viewsets
from api.models import LocationLog
from api.Serializers.location_log_serializer import LocationLogSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['LocationLogs'])
class LocationLogViewSet(viewsets.ModelViewSet):
    """ViewSet estándar para LocationLogs (Heat Map data)."""
    queryset = LocationLog.objects.all()
    serializer_class = LocationLogSerializer