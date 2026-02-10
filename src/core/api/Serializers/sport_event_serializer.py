from rest_framework import serializers
from api.models import SportEvent

class SportEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SportEvent
        fields = '__all__'