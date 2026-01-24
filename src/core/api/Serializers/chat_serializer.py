from rest_framework import serializers
from api.models import Chat

class ChatSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Chat
        fields = '__all__'