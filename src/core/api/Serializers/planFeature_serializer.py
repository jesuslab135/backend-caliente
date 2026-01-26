from rest_framework import serializers
from api.models import PlanFeature

class PlanFeatureSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = PlanFeature
        fields = '__all__'