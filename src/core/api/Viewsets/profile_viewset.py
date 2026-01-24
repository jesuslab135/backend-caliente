from rest_framework import viewsets
from api.models import Profile
from api.Serializers.profile_serializer import ProfileSerializer

from drf_spectacular.utils import extend_schema

@extend_schema(tags=['Profiles'])
class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer