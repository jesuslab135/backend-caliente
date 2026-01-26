from rest_framework import serializers
from api.models import Friendship

class FriendshipSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Friendship
        fields = '__all__'