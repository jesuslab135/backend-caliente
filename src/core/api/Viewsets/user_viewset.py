import logging
from rest_framework import viewsets
from api.models import User
from api.Serializers.user_serializer import UserSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['Users'])
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        safe_data = request.data.copy()
        if 'password' in safe_data:
            safe_data['password'] = '********'
            
        logger.info(f"Registering new user. Data: {safe_data}")
        
        try:
            response = super().create(request, *args, **kwargs)
            logger.info(f"User registered: ID {response.data.get('id')} - Email: {response.data.get('email')}")
            return response
        except Exception as e:
            logger.exception("Critical error in user registration") # .exception includes the full stacktrace
            raise e

    def update(self, request, *args, **kwargs):
        logger.info(f"Updating user ID {kwargs.get('pk')}")
        return super().update(request, *args, **kwargs)