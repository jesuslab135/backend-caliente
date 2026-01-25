import logging
from rest_framework import viewsets
from drf_spectacular.utils import extend_schema
from api.models import Chat
from api.Serializers.chat_serializer import ChatSerializer

logger = logging.getLogger('api')

@extend_schema(tags=['Chats'])
class ChatViewSet(viewsets.ModelViewSet):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer

    def create(self, request, *args, **kwargs):
        logger.info(f"User {request.user} attempting to initiate a new Chat")
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        logger.warning(f"Deleting Chat ID {kwargs.get('pk')} requested by {request.user}")
        return super().destroy(request, *args, **kwargs)