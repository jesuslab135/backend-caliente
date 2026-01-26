from rest_framework import serializers
from api.models import Coupon

class CouponSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Coupon
        fields = '__all__'