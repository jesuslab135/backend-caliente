from rest_framework import serializers
from api.models import PaymentMethod

class PaymentMethodSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = '__all__'