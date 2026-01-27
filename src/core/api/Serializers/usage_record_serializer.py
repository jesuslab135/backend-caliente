from rest_framework import serializers
from api.models import UsageRecord

class UsageRecordSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = UsageRecord
        fields = '__all__'