import logging
from rest_framework import viewsets
from api.models import BlitzVote
from api.Serializers.blitz_vote_serializer import BlitzVoteSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['BlitzVotes'])
class BlitzVoteViewSet(viewsets.ModelViewSet):
    """ViewSet estándar para BlitzVotes."""
    queryset = BlitzVote.objects.all()
    serializer_class = BlitzVoteSerializer