from rest_framework import serializers
from api.models import Blitz

class BlitzSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Blitz
        fields = '__all__'