from rest_framework import serializers
from api.models import ZoneStats

class ZoneStatsSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ZoneStats
        fields = '__all__'