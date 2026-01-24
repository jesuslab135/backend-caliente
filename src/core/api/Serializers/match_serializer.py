from rest_framework import serializers
from api.models import Match

class MatchSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Match
        fields = '__all__'