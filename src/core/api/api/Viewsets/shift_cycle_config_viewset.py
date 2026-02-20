from api.Serializers.shift_cycle_config_serializer import ShiftCycleConfigSerializer 
from api.models import ShiftCycleConfig

from rest_framework import viewsets

class ShiftCycleConfigViewSet(viewsets.ModelViewSet):
    queryset = ShiftCycleConfig.objects.all()
    serializer_class = ShiftCycleConfigSerializer