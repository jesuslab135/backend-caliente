import logging
from rest_framework import viewsets
from api.models import MeetupPlan
from api.Serializers.meetup_plan_serializer import MeetupPlanSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['MeetupPlans'])
class MeetupPlanViewSet(viewsets.ModelViewSet):
    """ViewSet estándar para MeetupPlans."""
    queryset = MeetupPlan.objects.all()
    serializer_class = MeetupPlanSerializer