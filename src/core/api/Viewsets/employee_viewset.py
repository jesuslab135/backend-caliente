from api.Serializers.employee_serializer import EmployeeSerializer
from api.models import Employee

from rest_framework import viewsets

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer