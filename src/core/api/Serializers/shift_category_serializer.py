from rest_framework import serializers
from api.models import ShiftCategory

class ShiftCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftCategory
        fields = '__all__'