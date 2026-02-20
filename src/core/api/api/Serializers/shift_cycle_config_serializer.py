from rest_framework import serializers
from api.models import ShiftCycleConfig

class ShiftCycleConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftCycleConfig
        fields = '__all__'