from api.Serializers.schedule_generation_log_serializer import ScheduleGenerationLogSerializer 
from api.models import ScheduleGenerationLog

from rest_framework import viewsets

class ScheduleGenerationLogViewSet(viewsets.ModelViewSet):
    queryset = ScheduleGenerationLog.objects.all()
    serializer_class = ScheduleGenerationLogSerializer