from api.Serializers.team_serializer import TeamSerializer 
from api.models import Team

from rest_framework import viewsets

class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    lookup_field = 'uuid'