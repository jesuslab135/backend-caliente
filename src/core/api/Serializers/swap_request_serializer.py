from django.contrib.auth.models import User
from rest_framework import serializers
from api.models import SwapRequest, Employee, Schedule, ShiftType


# ── Nested read serializers matching frontend DTOs ──────────

class _UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class _EmployeeSummarySerializer(serializers.ModelSerializer):
    user = _UserSummarySerializer(read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'uuid', 'employee_id', 'user']


class _ShiftTypeSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftType
        fields = ['id', 'code', 'name', 'start_time', 'end_time']


class _ScheduleSummarySerializer(serializers.ModelSerializer):
    shift_type = _ShiftTypeSummarySerializer(read_only=True)

    class Meta:
        model = Schedule
        fields = ['id', 'uuid', 'date', 'shift_type']


# ── Read serializer ─────────────────────────────────────────

class SwapRequestSerializer(serializers.ModelSerializer):
    """Read serializer — nests employee and schedule summaries."""
    requester = _EmployeeSummarySerializer(read_only=True)
    target_employee = _EmployeeSummarySerializer(read_only=True)
    requester_schedule = _ScheduleSummarySerializer(read_only=True)
    target_schedule = _ScheduleSummarySerializer(read_only=True)

    class Meta:
        model = SwapRequest
        fields = '__all__'


class SwapRequestCreateSerializer(serializers.Serializer):
    """
    Write serializer for creating swap requests.

    Accepts trader-friendly input:
      - target_employee: UUID of the target employee
      - requester_date: date string (YYYY-MM-DD) of the requester's shift
      - target_date: date string (YYYY-MM-DD) of the target's shift
      - reason: optional text

    Resolves UUIDs + dates → actual Schedule FK records.
    The requester is auto-set from the authenticated user.
    """
    target_employee = serializers.UUIDField()
    requester_date = serializers.DateField()
    target_date = serializers.DateField()
    reason = serializers.CharField(required=False, default='', allow_blank=True)

    def validate_target_employee(self, value):
        try:
            return Employee.objects.get(uuid=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError('No se encontró el empleado.')

    def validate(self, attrs):
        request = self.context['request']

        # Resolve requester from authenticated user
        try:
            requester = request.user.employee_profile
        except Employee.DoesNotExist:
            raise serializers.ValidationError({'requester': 'Tu usuario no tiene un perfil de empleado.'})

        target = attrs['target_employee']

        if requester.pk == target.pk:
            raise serializers.ValidationError({'target_employee': 'No puedes solicitar un intercambio contigo mismo.'})

        # Find requester's schedule for that date
        requester_schedule = Schedule.objects.filter(
            employee=requester,
            date=attrs['requester_date'],
        ).first()
        if not requester_schedule:
            raise serializers.ValidationError({
                'requester_date': f'No tienes un turno asignado el {attrs["requester_date"]}.'
            })

        # Find target's schedule for that date
        target_schedule = Schedule.objects.filter(
            employee=target,
            date=attrs['target_date'],
        ).first()
        if not target_schedule:
            raise serializers.ValidationError({
                'target_date': f'El compañero no tiene un turno asignado el {attrs["target_date"]}.'
            })

        attrs['requester'] = requester
        attrs['target_employee'] = target
        attrs['requester_schedule'] = requester_schedule
        attrs['target_schedule'] = target_schedule
        return attrs

    def create(self, validated_data):
        return SwapRequest.objects.create(
            requester=validated_data['requester'],
            requester_schedule=validated_data['requester_schedule'],
            target_employee=validated_data['target_employee'],
            target_schedule=validated_data['target_schedule'],
            reason=validated_data.get('reason', ''),
        )
