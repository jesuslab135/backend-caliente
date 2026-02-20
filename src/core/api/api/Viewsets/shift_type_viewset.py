from api.Serializers.shift_type_serializer import ShiftTypeSerializer 
from api.models import ShiftType

from rest_framework import viewsets

class ShiftTypeViewSet(viewsets.ModelViewSet):
    queryset = ShiftType.objects.all()
    serializer_class = ShiftTypeSerializer