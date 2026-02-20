from api.Serializers.schedule_serializer import ScheduleSerializer
from api.Serializers.schedule_generation_log_serializer import ScheduleGenerationLogSerializer
from api.models import Schedule
from api.services.schedule_generator import ScheduleGenerator

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated


class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    lookup_field = 'uuid'

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """
        POST /api/schedules/generate/
        Genera horarios mensuales usando el algoritmo de auto-asignacion.
        Solo administradores pueden ejecutar esta accion.
        """
        # RBAC: solo admin
        user = request.user
        if not hasattr(user, 'employee_profile') or user.employee_profile.role != 'ADMIN':
            return Response(
                {'detail': 'Solo administradores pueden generar horarios.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        month = request.data.get('month')
        year = request.data.get('year')

        # Validar params
        if not month or not year:
            return Response(
                {'detail': 'Los campos month y year son requeridos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            month = int(month)
            year = int(year)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'month y year deben ser numeros enteros.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if month < 1 or month > 12:
            return Response(
                {'detail': 'Mes invalido (debe ser 1-12).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if year < 2020 or year > 2100:
            return Response(
                {'detail': 'Ano invalido (debe ser 2020-2100).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ejecutar generacion
        generator = ScheduleGenerator(month, year, user)
        log = generator.generate()

        serializer = ScheduleGenerationLogSerializer(log)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
