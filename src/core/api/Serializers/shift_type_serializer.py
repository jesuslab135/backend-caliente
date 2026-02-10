from rest_framework import serializers
from api.models import ShiftType

class ShiftTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftType
        fields = '__all__'