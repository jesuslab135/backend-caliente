"""
Management command: seed_users
==============================
Carga datos semilla para pruebas: 3 usuarios (Admin, Manager, Trader),
un equipo y las categorías de turno del SRS.

Uso:
    python manage.py seed_users

Idempotente: usa get_or_create, se puede ejecutar múltiples veces sin duplicar.
"""

from datetime import time, date
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import Employee, Team, ShiftCategory


class Command(BaseCommand):
    help = 'Carga datos semilla: 3 usuarios, 1 equipo y 4 categorías de turno'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== SEED: Datos Semilla para Caliente Scheduler ===\n'))

        # ── 1. Shift Categories (del SRS) ──────────────────────────────
        self.stdout.write('Creando categorías de turno...')
        categories_data = [
            {'code': 'AM',  'name': 'Turno Mañana',    'min_traders': 3, 'typical_start_time': time(6, 0),  'typical_end_time': time(14, 0), 'display_order': 1},
            {'code': 'INS', 'name': 'Turno Swing',      'min_traders': 0, 'typical_start_time': time(9, 0),  'typical_end_time': time(18, 0), 'display_order': 2},
            {'code': 'MID', 'name': 'Turno Tarde',      'min_traders': 3, 'typical_start_time': time(14, 0), 'typical_end_time': time(22, 0), 'display_order': 3},
            {'code': 'NS',  'name': 'Turno Nocturno',   'min_traders': 1, 'typical_start_time': time(22, 0), 'typical_end_time': time(6, 0),  'display_order': 4},
        ]
        for cat_data in categories_data:
            obj, created = ShiftCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults=cat_data,
            )
            status = 'CREADA' if created else 'ya existe'
            self.stdout.write(f'  [{status}] ShiftCategory: {obj.code} - {obj.name}')

        # ── 2. Team ────────────────────────────────────────────────────
        self.stdout.write('\nCreando equipo...')
        team, team_created = Team.objects.get_or_create(
            name='Trading Floor A',
            defaults={
                'description': 'Equipo principal de traders - Monitor e In-Play',
                'is_active': True,
            },
        )
        status = 'CREADO' if team_created else 'ya existe'
        self.stdout.write(f'  [{status}] Team: {team.name}')

        # ── 3. Usuarios + Employees ────────────────────────────────────
        self.stdout.write('\nCreando usuarios y empleados...')

        PASSWORD = 'Test1234!'

        users_data = [
            {
                'user': {
                    'username': 'admin.caliente',
                    'first_name': 'Ricardo',
                    'last_name': 'Mendoza Ríos',
                    'email': 'admin@caliente.mx',
                    'is_staff': True,
                    'is_superuser': False,
                },
                'employee': {
                    'employee_id': 'EMP-001',
                    'role': Employee.Role.ADMIN,
                    'phone': '+526441234001',
                    'hire_date': date(2022, 1, 15),
                    'team': None,  # Admin no pertenece a un team operativo
                },
            },
            {
                'user': {
                    'username': 'manager.caliente',
                    'first_name': 'Alejandra',
                    'last_name': 'Vega Torres',
                    'email': 'manager@caliente.mx',
                    'is_staff': False,
                    'is_superuser': False,
                },
                'employee': {
                    'employee_id': 'EMP-002',
                    'role': Employee.Role.MANAGER,
                    'phone': '+526441234002',
                    'hire_date': date(2022, 6, 1),
                    'team': team,
                },
            },
            {
                'user': {
                    'username': 'trader.caliente',
                    'first_name': 'Carlos',
                    'last_name': 'Ramírez Luna',
                    'email': 'trader@caliente.mx',
                    'is_staff': False,
                    'is_superuser': False,
                },
                'employee': {
                    'employee_id': 'EMP-003',
                    'role': Employee.Role.MONITOR_TRADER,
                    'phone': '+526441234003',
                    'hire_date': date(2023, 3, 10),
                    'team': team,
                },
            },
        ]

        manager_employee = None

        for data in users_data:
            user_fields = data['user']
            emp_fields = data['employee']

            # Crear o recuperar User
            user, user_created = User.objects.get_or_create(
                username=user_fields['username'],
                defaults={
                    'first_name': user_fields['first_name'],
                    'last_name': user_fields['last_name'],
                    'email': user_fields['email'],
                    'is_staff': user_fields['is_staff'],
                    'is_superuser': user_fields['is_superuser'],
                },
            )
            if user_created:
                user.set_password(PASSWORD)
                user.save()

            u_status = 'CREADO' if user_created else 'ya existe'
            self.stdout.write(f'  [{u_status}] User: {user.username} ({user.email})')

            # Crear o recuperar Employee
            employee, emp_created = Employee.objects.get_or_create(
                employee_id=emp_fields['employee_id'],
                defaults={
                    'user': user,
                    'role': emp_fields['role'],
                    'phone': emp_fields['phone'],
                    'hire_date': emp_fields['hire_date'],
                    'team': emp_fields['team'],
                    'is_active': True,
                },
            )
            e_status = 'CREADO' if emp_created else 'ya existe'
            self.stdout.write(f'  [{e_status}] Employee: {employee.employee_id} - {employee.full_name} (role={employee.role})')

            # Guardar referencia al manager
            if emp_fields['role'] == Employee.Role.MANAGER:
                manager_employee = employee

        # ── 4. Asignar Manager como líder del Team ─────────────────────
        if manager_employee and not team.manager:
            team.manager = manager_employee
            team.save()
            self.stdout.write(f'\n  Team "{team.name}" → Manager: {manager_employee.full_name}')

        # ── Resumen ────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS('\n✓ Seed completado exitosamente.'))
        self.stdout.write(self.style.SUCCESS(f'  Contraseña para los 3 usuarios: {PASSWORD}'))
        self.stdout.write(self.style.SUCCESS('  Ejecuta: python manage.py runserver\n'))
