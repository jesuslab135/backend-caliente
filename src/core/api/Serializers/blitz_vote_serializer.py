from rest_framework import serializers
from api.models import BlitzVote

class BlitzVoteSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = BlitzVote
        fields = '__all__'