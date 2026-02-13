from api.Serializers.employee_serializer import EmployeeSerializer
from api.models import Employee

from rest_framework import viewsets


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related('user', 'team').all()
    serializer_class = EmployeeSerializer
