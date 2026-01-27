from rest_framework import serializers
from api.models import WebhookLog

class WebhookLogSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = WebhookLog
        fields = '__all__'