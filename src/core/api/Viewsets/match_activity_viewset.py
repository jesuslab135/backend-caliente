import logging
from rest_framework import viewsets
from api.models import MatchActivity
from api.Serializers.match_activity_serializer import MatchActivitySerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['MatchActivities'])
class MatchActivityViewSet(viewsets.ModelViewSet):
    """ViewSet estándar para MatchActivitys."""
    queryset = MatchActivity.objects.all()
    serializer_class = MatchActivitySerializer