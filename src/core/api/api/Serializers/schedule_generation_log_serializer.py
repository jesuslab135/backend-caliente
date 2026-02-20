from rest_framework import serializers
from api.models import ScheduleGenerationLog

class ScheduleGenerationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleGenerationLog
        fields = '__all__'