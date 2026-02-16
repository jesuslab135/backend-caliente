from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.Serializers.vacation_serializer import (
    VacationSerializer,
    VacationCreateSerializer,
)
from api.models import Vacation


class VacationViewSet(viewsets.ModelViewSet):
    queryset = Vacation.objects.select_related('employee__user').all()
    serializer_class = VacationSerializer
    lookup_field = 'uuid'

    def get_serializer_class(self):
        if self.action == 'create':
            return VacationCreateSerializer
        return VacationSerializer

    def create(self, request, *args, **kwargs):
        serializer = VacationCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        vacation = serializer.save()
        return Response(
            VacationSerializer(vacation).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['put'], url_path='approve')
    def approve(self, request, uuid=None):
        """
        PUT /api/vacations/<uuid>/approve/
        Admin approve/reject a vacation request.
        Body: { action: 'approve' | 'reject', rejection_reason?: string }
        """
        vacation = self.get_object()

        if vacation.status != 'PENDING':
            return Response(
                {'detail': 'Solo se pueden procesar solicitudes pendientes.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action_val = request.data.get('action')
        if action_val not in ('approve', 'reject'):
            return Response(
                {'detail': 'El campo "action" debe ser "approve" o "reject".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        vacation.approved_by = request.user
        vacation.approved_at = timezone.now()

        if action_val == 'approve':
            vacation.status = 'APPROVED'
        else:
            vacation.status = 'REJECTED'
            vacation.rejection_reason = request.data.get('rejection_reason', '')

        vacation.save()
        return Response(VacationSerializer(vacation).data)
