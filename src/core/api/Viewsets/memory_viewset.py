import logging
from rest_framework import viewsets
from api.models import Memory
from api.Serializers.memory_serializer import MemorySerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['Memories'])
class MemoryViewSet(viewsets.ModelViewSet):
    """ViewSet estándar para Memories."""
    queryset = Memory.objects.all()
    serializer_class = MemorySerializer