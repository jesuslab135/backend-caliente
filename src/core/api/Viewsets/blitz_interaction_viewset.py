import logging
from rest_framework import viewsets
from api.models import BlitzInteraction
from backend.src.core.api.Serializers.blitz_interaction_serializer import BlitzInteractionSerializer 
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['Blitzs Interactions'])
class BlitzInteractionViewSet(viewsets.ModelViewSet):
    queryset = BlitzInteraction.objects.all()
    serializer_class = BlitzInteractionSerializer

    def create(self, request, *args, **kwargs):
        logger.info(f"Initiating Blitz interaction event by user: {request.user}")
        try:
            response = super().create(request, *args, **kwargs)
            logger.info(f"Blitz interaction created successfully: ID {response.data.get('id')}")
            return response
        except Exception as e:
            logger.error(f"Failed to create Blitz interaction: {str(e)}")
            raise e