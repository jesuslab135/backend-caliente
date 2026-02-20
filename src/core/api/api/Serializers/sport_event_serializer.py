from rest_framework import serializers
from api.models import SportEvent


class SportEventSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    league_name = serializers.CharField(source='league.name', read_only=True)
    sport = serializers.CharField(source='league.sport', read_only=True)

    class Meta:
        model = SportEvent
        fields = '__all__'
