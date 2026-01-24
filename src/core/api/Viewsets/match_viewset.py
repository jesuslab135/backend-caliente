from rest_framework import viewsets
from api.models import Match
from api.Serializers.match_serializer import MatchSerializer

from drf_spectacular.utils import extend_schema

@extend_schema(tags=['Matchs'])
class MatchViewSet(viewsets.ModelViewSet):
    queryset = Match.objects.all()
    serializer_class = MatchSerializer