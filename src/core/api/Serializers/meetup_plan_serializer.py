from rest_framework import serializers
from api.models import MeetupPlan

class MeetupPlanSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = MeetupPlan
        fields = '__all__'