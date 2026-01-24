from rest_framework import viewsets
from api.models import User
from api.Serializers.user_serializer import UserSerializer

from drf_spectacular.utils import extend_schema

@extend_schema(tags=['Users'])
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer