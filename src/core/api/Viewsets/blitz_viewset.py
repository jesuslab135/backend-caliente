import logging
from rest_framework import viewsets
from api.models import Blitz
from api.Serializers.blitz_serializer import BlitzSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['Blitzs'])
class BlitzViewSet(viewsets.ModelViewSet):
    queryset = Blitz.objects.all()
    serializer_class = BlitzSerializer

    def create(self, request, *args, **kwargs):
        logger.info(f"Initiating Blitz event by user: {request.user}")
        try:
            response = super().create(request, *args, **kwargs)
            logger.info(f"Blitz created successfully: ID {response.data.get('id')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create Blitz: {str(e)}")
            raise e