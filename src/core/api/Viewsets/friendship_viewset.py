import logging
from rest_framework import viewsets
from api.models import Friendship
from api.Serializers.friendship_serializer import FriendshipSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['Friendships'])
class FriendshipViewSet(viewsets.ModelViewSet):
    """ViewSet estándar para Friendships."""
    queryset = Friendship.objects.all()
    serializer_class = FriendshipSerializer