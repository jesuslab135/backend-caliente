from rest_framework import viewsets
from api.models import Message
from api.Serializers.message_serializer import MessageSerializer

from drf_spectacular.utils import extend_schema

@extend_schema(tags=['Messages'])
class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer