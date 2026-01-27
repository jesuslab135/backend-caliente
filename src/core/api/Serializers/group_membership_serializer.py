from rest_framework import serializers
from api.models import GroupMembership

class GroupMembershipSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = GroupMembership
        fields = '__all__'