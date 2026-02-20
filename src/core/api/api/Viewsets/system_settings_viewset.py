from api.Serializers.system_settings_serializer import SystemSettingsSerializer 
from api.models import SystemSettings

from rest_framework import viewsets

class SystemSettingsViewSet(viewsets.ModelViewSet):
    queryset = SystemSettings.objects.all()
    serializer_class = SystemSettingsSerializer