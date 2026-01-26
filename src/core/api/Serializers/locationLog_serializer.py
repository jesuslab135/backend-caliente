from rest_framework import serializers
from api.models import LocationLog

class LocationLogSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = LocationLog
        fields = '__all__'