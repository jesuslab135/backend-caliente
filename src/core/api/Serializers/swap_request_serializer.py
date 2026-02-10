from rest_framework import serializers
from api.models import SwapRequest

class SwapRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SwapRequest
        fields = '__all__'