from rest_framework import serializers
from api.models import MatchActivity

class MatchActivitySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = MatchActivity
        fields = '__all__'