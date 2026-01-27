import logging
from rest_framework import viewsets
from api.models import MemoryPhoto
from api.Serializers.memory_photo_serializer import MemoryPhotoSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['MemoryPhotos'])
class MemoryPhotoViewSet(viewsets.ModelViewSet):
    """ViewSet estándar para MemoryPhotos."""
    queryset = MemoryPhoto.objects.all()
    serializer_class = MemoryPhotoSerializer