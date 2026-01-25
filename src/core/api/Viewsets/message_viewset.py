import logging
from rest_framework import viewsets
from drf_spectacular.utils import extend_schema
from api.models import Message
from api.Serializers.message_serializer import MessageSerializer

logger = logging.getLogger('api')

@extend_schema(tags=['Messages'])
class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer

    def create(self, request, *args, **kwargs):
        metadata = {k: v for k, v in request.data.items() if k != 'content'} 
        logger.info(f"Sending message. Metadata: {metadata}")
        
        return super().create(request, *args, **kwargs)