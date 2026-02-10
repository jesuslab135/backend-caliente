from api.Serializers.sport_event_serializer import SportEventSerializer 
from api.models import SportEvent

from rest_framework import viewsets

class SportEventViewSet(viewsets.ModelViewSet):
    queryset = SportEvent.objects.all()
    serializer_class = SportEventSerializer