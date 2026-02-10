from api.Serializers.schedule_serializer import ScheduleSerializer 
from api.models import Schedule

from rest_framework import viewsets

class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer