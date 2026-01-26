from rest_framework import serializers
from api.models import Discount

class DiscountSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Discount
        fields = '__all__'