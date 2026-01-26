from rest_framework import serializers
from api.models import Subscription

class SubscriptionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'