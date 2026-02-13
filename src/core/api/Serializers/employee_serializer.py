from django.contrib.auth.models import User
from rest_framework import serializers
from api.models import Employee, Team


class EmployeeUserNestedSerializer(serializers.ModelSerializer):
    """Nested User fields returned inside each Employee."""

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']
        read_only_fields = fields


class EmployeeTeamNestedSerializer(serializers.ModelSerializer):
    """Nested Team summary returned inside each Employee."""

    class Meta:
        model = Team
        fields = ['uuid', 'name']
        read_only_fields = fields


class EmployeeSerializer(serializers.ModelSerializer):
    user = EmployeeUserNestedSerializer(read_only=True)
    team = EmployeeTeamNestedSerializer(read_only=True)

    class Meta:
        model = Employee
        fields = '__all__'
