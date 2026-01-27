from rest_framework import serializers
from api.models import MemoryPhoto

class MemoryPhotoSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = MemoryPhoto
        fields = '__all__'