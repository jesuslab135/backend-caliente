from api.Serializers.swap_request_serializer import SwapRequestSerializer 
from api.models import SwapRequest


from rest_framework import viewsets

class SwapRequestViewSet(viewsets.ModelViewSet):
    queryset = SwapRequest.objects.all()
    serializer_class = SwapRequestSerializer