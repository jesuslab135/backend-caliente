from api.Serializers.shift_category_serializer import ShiftCategorySerializer 
from api.models import ShiftCategory

from rest_framework import viewsets

class ShiftCategoryViewSet(viewsets.ModelViewSet):
    queryset = ShiftCategory.objects.all()
    serializer_class = ShiftCategorySerializer