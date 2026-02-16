from api.Serializers.vacation_serializer import VacationSerializer 
from api.models import Vacation

from rest_framework import viewsets

class VacationViewSet(viewsets.ModelViewSet):
    queryset = Vacation.objects.all()
    serializer_class = VacationSerializer
    lookup_field = 'uuid'