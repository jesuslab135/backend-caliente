from rest_framework import viewsets
from api.models import Group
from api.Serializers.group_serializer import GroupSerializer

from drf_spectacular.utils import extend_schema

@extend_schema(tags=['Groups'])
class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer