from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from api.Serializers.swap_request_serializer import (
    SwapRequestSerializer,
    SwapRequestCreateSerializer,
    _ScheduleSummarySerializer,
)
from api.models import SwapRequest, Employee, Schedule


class SwapRequestViewSet(viewsets.ModelViewSet):
    queryset = SwapRequest.objects.select_related(
        'requester__user',
        'target_employee__user',
        'requester_schedule__shift_type',
        'target_schedule__shift_type',
    ).all()
    serializer_class = SwapRequestSerializer
    lookup_field = 'uuid'

    def get_serializer_class(self):
        if self.action == 'create':
            return SwapRequestCreateSerializer
        return SwapRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = SwapRequestCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        swap = serializer.save()
        # Return full read representation
        return Response(
            SwapRequestSerializer(swap).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='lookup-schedule')
    def lookup_schedule(self, request):
        """
        GET /api/swaprequests/lookup-schedule/?employee_uuid=...&date=YYYY-MM-DD
        Returns the schedule (with nested shift_type) for a given employee+date.
        Used by the create modal to preview shifts before submitting.
        """
        emp_uuid = request.query_params.get('employee_uuid')
        date = request.query_params.get('date')

        if not emp_uuid or not date:
            return Response(
                {'detail': 'Se requieren employee_uuid y date.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee = Employee.objects.get(uuid=emp_uuid)
        except Employee.DoesNotExist:
            return Response(
                {'detail': 'Empleado no encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        schedule = Schedule.objects.select_related('shift_type').filter(
            employee=employee,
            date=date,
        ).first()

        if not schedule:
            return Response(
                {'detail': 'Sin turno asignado en esa fecha.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(_ScheduleSummarySerializer(schedule).data)

    @action(detail=True, methods=['put'], url_path='respond')
    def respond(self, request, uuid=None):
        """
        PUT /api/swaprequests/<uuid>/respond/
        Peer accept/reject. Only the target_employee can respond.
        Body: { action: 'accept' | 'reject', peer_response_note?: string }
        """
        swap = self.get_object()

        if swap.status != 'PENDING':
            return Response(
                {'detail': 'Esta solicitud ya no está pendiente.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify caller is the target employee
        try:
            caller = request.user.employee_profile
        except Exception:
            return Response(
                {'detail': 'Tu usuario no tiene un perfil de empleado.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if caller.pk != swap.target_employee_id:
            return Response(
                {'detail': 'Solo el compañero destinatario puede responder.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        action_val = request.data.get('action')
        if action_val not in ('accept', 'reject'):
            return Response(
                {'detail': 'El campo "action" debe ser "accept" o "reject".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        swap.peer_response_at = timezone.now()
        swap.peer_response_note = request.data.get('peer_response_note', '')

        if action_val == 'accept':
            swap.status = 'ACCEPTED_BY_PEER'
        else:
            swap.status = 'REJECTED_BY_PEER'

        swap.save()
        return Response(SwapRequestSerializer(swap).data)

    @action(detail=True, methods=['put'], url_path='approve')
    def approve(self, request, uuid=None):
        """
        PUT /api/swaprequests/<uuid>/approve/
        Admin approve/reject. Only after peer has accepted.
        Body: { action: 'approve' | 'reject', admin_response_note?: string }
        """
        swap = self.get_object()

        if swap.status != 'ACCEPTED_BY_PEER':
            return Response(
                {'detail': 'Solo se pueden aprobar solicitudes aceptadas por el compañero.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action_val = request.data.get('action')
        if action_val not in ('approve', 'reject'):
            return Response(
                {'detail': 'El campo "action" debe ser "approve" o "reject".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        swap.admin_response_at = timezone.now()
        swap.admin_responder = request.user
        swap.admin_response_note = request.data.get('admin_response_note', '')

        if action_val == 'approve':
            swap.status = 'APPROVED'
            # Swap the actual schedules
            self._execute_swap(swap)
        else:
            swap.status = 'REJECTED_BY_ADMIN'

        swap.save()
        return Response(SwapRequestSerializer(swap).data)

    def _execute_swap(self, swap):
        """Swap the shift_type between requester and target schedules."""
        sched_a = swap.requester_schedule
        sched_b = swap.target_schedule
        sched_a.shift_type, sched_b.shift_type = sched_b.shift_type, sched_a.shift_type
        sched_a.edit_source = 'SWAP'
        sched_b.edit_source = 'SWAP'
        sched_a.save()
        sched_b.save()
