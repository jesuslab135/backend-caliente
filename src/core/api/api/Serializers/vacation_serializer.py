from django.contrib.auth.models import User
from rest_framework import serializers
from api.models import Vacation, Employee


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


# ── Read serializer ─────────────────────────────────────────

class VacationSerializer(serializers.ModelSerializer):
    """Read serializer — nests employee summary + computed total_days."""
    employee = _EmployeeSummarySerializer(read_only=True)
    total_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = Vacation
        fields = '__all__'


# ── Write serializer (create) ───────────────────────────────

class VacationCreateSerializer(serializers.Serializer):
    """
    Write serializer for creating vacation requests.
    Auto-sets employee from the authenticated user.
    """
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(required=False, default='', allow_blank=True)

    def validate(self, attrs):
        request = self.context['request']

        # Resolve employee from authenticated user
        try:
            employee = request.user.employee_profile
        except Employee.DoesNotExist:
            raise serializers.ValidationError({'employee': 'Tu usuario no tiene un perfil de empleado.'})

        if attrs['end_date'] < attrs['start_date']:
            raise serializers.ValidationError({
                'end_date': 'La fecha de fin no puede ser anterior a la fecha de inicio.'
            })

        # Check for overlapping approved vacations
        overlapping = Vacation.objects.filter(
            employee=employee,
            status='APPROVED',
            start_date__lte=attrs['end_date'],
            end_date__gte=attrs['start_date'],
        )
        if overlapping.exists():
            raise serializers.ValidationError({
                'start_date': 'Ya tienes vacaciones aprobadas que se solapan con este período.'
            })

        attrs['employee'] = employee
        return attrs

    def create(self, validated_data):
        return Vacation.objects.create(
            employee=validated_data['employee'],
            start_date=validated_data['start_date'],
            end_date=validated_data['end_date'],
            reason=validated_data.get('reason', ''),
        )
