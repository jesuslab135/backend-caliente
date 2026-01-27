import logging
from rest_framework import viewsets
from api.models import GroupMembership
from api.Serializers.group_membership_serializer import GroupMembershipSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['GroupMemberships'])
class GroupMembershipViewSet(viewsets.ModelViewSet):
    """ViewSet estándar para GroupMemberships."""
    queryset = GroupMembership.objects.all()
    serializer_class = GroupMembershipSerializer