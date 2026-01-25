import logging
from rest_framework import viewsets
from drf_spectacular.utils import extend_schema
from api.models import Match
from api.Serializers.match_serializer import MatchSerializer

logger = logging.getLogger('api')

@extend_schema(tags=['Matchs'])
class MatchViewSet(viewsets.ModelViewSet):
    queryset = Match.objects.all()
    serializer_class = MatchSerializer

    def create(self, request, *args, **kwargs):
        logger.info(f"New Match generated. Data: {request.data}")
        try:
            response = super().create(request, *args, **kwargs)
            logger.info(f"Match confirmed and saved: ID {response.data.get('id')}")
            return response
        except Exception as e:
            logger.exception("Error critical in the Match process")
            raise e