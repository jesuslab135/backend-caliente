from api.Serializers.league_serializer import LeagueSerializer
from api.models import League

from rest_framework import viewsets

class LeagueViewSet(viewsets.ModelViewSet):
    queryset = League.objects.all()
    serializer_class = LeagueSerializer
    lookup_field = 'uuid'