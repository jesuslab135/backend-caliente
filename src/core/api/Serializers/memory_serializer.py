from rest_framework import serializers
from api.models import Memory

class MemorySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Memory
        fields = '__all__'