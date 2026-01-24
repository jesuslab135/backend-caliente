from rest_framework import viewsets
from api.models import Blitz
from api.Serializers.blitz_serializer import BlitzSerializer

from drf_spectacular.utils import extend_schema

@extend_schema(tags=['Blitzs'])
class BlitzViewSet(viewsets.ModelViewSet):
    queryset = Blitz.objects.all()
    serializer_class = BlitzSerializer