import logging
from rest_framework import viewsets
from api.models import Group
from api.Serializers.group_serializer import GroupSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['Groups'])
class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

    def list(self, request, *args, **kwargs):
        logger.debug(f"Listing all groups by: {request.user}")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        logger.info(f"Initiating group creation. Payload: {request.data}")
        try:
            response = super().create(request, *args, **kwargs)
            logger.info(f"Group created successfully: ID {response.data.get('id')} - Name: {response.data.get('name')}")
            return response
        except Exception as e:
            logger.error(f"Error creating group: {str(e)}")
            raise e
        
    def destroy(self, request, *args, **kwargs):
        instance_id = kwargs.get('pk')
        logger.warning(f"Deletion request for Group ID: {instance_id} by user {request.user}")
        return super().destroy(request, *args, **kwargs)