from rest_framework import viewsets
from api.models import Chat
from api.Serializers.chat_serializer import ChatSerializer

from drf_spectacular.utils import extend_schema

@extend_schema(tags=['Chats'])
class ChatViewSet(viewsets.ModelViewSet):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer