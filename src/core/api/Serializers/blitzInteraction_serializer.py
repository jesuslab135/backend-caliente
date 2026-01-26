from rest_framework import serializers
from api.models import BlitzInteraction

class BlitzInteractionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = BlitzInteraction
        fields = '__all__'