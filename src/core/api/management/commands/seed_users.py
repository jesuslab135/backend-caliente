"""
Management command: seed_users
==============================
Flushes ALL application data and seeds production data from scratch:
ShiftCategories, ShiftTypes, Team, Users + Employees.

Safe to run multiple times — always produces a clean, consistent state.

Usage:
    python manage.py seed_users
"""

from datetime import time
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import (
    Employee, Team, ShiftCategory, ShiftType,
    Schedule, SwapRequest, Vacation, ShiftCycleConfig,
    League, SportEvent, SystemSettings, ScheduleGenerationLog,
)


class Command(BaseCommand):
    help = 'Flushes all data and seeds production: 6 categories, 21 shift types, 1 team, 17 users/employees'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n=== SEED: Production Data for Caliente Scheduler ===\n'
        ))

        # ── 0. FLUSH all application data ──────────────────────────────
        self.stdout.write(self.style.WARNING('--- Flushing all existing data ---'))

        # Delete in FK-safe order (children before parents)
        flush_order = [
            ('ScheduleGenerationLog', ScheduleGenerationLog),
            ('SwapRequest',           SwapRequest),
            ('Schedule',              Schedule),
            ('Vacation',              Vacation),
            ('ShiftCycleConfig',      ShiftCycleConfig),
            ('SportEvent',            SportEvent),
            ('League',                League),
            ('SystemSettings',        SystemSettings),
        ]
        for label, model in flush_order:
            count, _ = model.objects.all().delete()
            self.stdout.write(f'  [DELETED] {label}: {count} records')

        # Clear Team.manager FK before deleting Employees
        Team.objects.all().update(manager=None)

        # Delete Employees, then their Users (non-superuser)
        emp_count, _ = Employee.objects.all().delete()
        self.stdout.write(f'  [DELETED] Employee: {emp_count} records')

        user_count, _ = User.objects.filter(is_superuser=False).delete()
        self.stdout.write(f'  [DELETED] User (non-superuser): {user_count} records')

        # Now safe to delete ShiftTypes, ShiftCategories, Teams
        st_count, _ = ShiftType.objects.all().delete()
        self.stdout.write(f'  [DELETED] ShiftType: {st_count} records')

        sc_count, _ = ShiftCategory.objects.all().delete()
        self.stdout.write(f'  [DELETED] ShiftCategory: {sc_count} records')

        team_count, _ = Team.objects.all().delete()
        self.stdout.write(f'  [DELETED] Team: {team_count} records')

        self.stdout.write(self.style.WARNING('  Flush complete.\n'))

        # ── 1. Shift Categories (6) ──────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('--- Shift Categories ---'))

        categories_data = [
            {'code': 'AM',     'name': 'Turno Manana',    'min_traders': 3, 'typical_start_time': time(6, 0),  'typical_end_time': time(14, 0), 'display_order': 1},
            {'code': 'INS',    'name': 'Turno Swing',      'min_traders': 0, 'typical_start_time': time(9, 0),  'typical_end_time': time(18, 0), 'display_order': 2},
            {'code': 'MID',    'name': 'Turno Tarde',      'min_traders': 3, 'typical_start_time': time(14, 0), 'typical_end_time': time(22, 0), 'display_order': 3},
            {'code': 'NS',     'name': 'Turno Nocturno',   'min_traders': 1, 'typical_start_time': time(22, 0), 'typical_end_time': time(6, 0),  'display_order': 4},
            {'code': 'HO',     'name': 'Home Office',      'min_traders': 0, 'typical_start_time': time(6, 0),  'typical_end_time': time(22, 0), 'display_order': 5},
            {'code': 'STATUS', 'name': 'Status Codes',     'min_traders': 0, 'typical_start_time': None,        'typical_end_time': None,        'display_order': 99},
        ]

        cat_created_count = 0
        for cat_data in categories_data:
            obj, created = ShiftCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults=cat_data,
            )
            cat_created_count += int(created)
            status = 'CREATED' if created else 'exists'
            self.stdout.write(f'  [{status}] ShiftCategory: {obj.code} - {obj.name}')

        # ── 2. Shift Types (17 working + 4 status) ───────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Shift Types ---'))

        # Look up categories by code for FK references
        cat_am = ShiftCategory.objects.get(code='AM')
        cat_ins = ShiftCategory.objects.get(code='INS')
        cat_mid = ShiftCategory.objects.get(code='MID')
        cat_ns = ShiftCategory.objects.get(code='NS')
        cat_ho = ShiftCategory.objects.get(code='HO')

        # Working shifts (is_working_shift=True)
        working_shifts = [
            {'code': 'MON6',      'name': 'Monitor 6AM',       'start_time': time(6, 0),  'end_time': time(14, 0), 'category': cat_am,  'applicable_to_monitor': True,  'applicable_to_inplay': False, 'color_code': '#3B82F6'},
            {'code': 'MON12',     'name': 'Monitor 12PM',      'start_time': time(12, 0), 'end_time': time(20, 0), 'category': cat_mid, 'applicable_to_monitor': True,  'applicable_to_inplay': False, 'color_code': '#2563EB'},
            {'code': 'MON14',     'name': 'Monitor 2PM',       'start_time': time(14, 0), 'end_time': time(22, 0), 'category': cat_mid, 'applicable_to_monitor': True,  'applicable_to_inplay': False, 'color_code': '#1D4ED8'},
            {'code': 'IP6',       'name': 'In-Play 6AM',       'start_time': time(6, 0),  'end_time': time(14, 0), 'category': cat_am,  'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#10B981'},
            {'code': 'IP9',       'name': 'In-Play 9AM',       'start_time': time(9, 0),  'end_time': time(17, 0), 'category': cat_ins, 'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#059669'},
            {'code': 'IP12',      'name': 'In-Play 12PM',      'start_time': time(12, 0), 'end_time': time(20, 0), 'category': cat_mid, 'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#047857'},
            {'code': 'IP14',      'name': 'In-Play 2PM',       'start_time': time(14, 0), 'end_time': time(22, 0), 'category': cat_mid, 'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#065F46'},
            {'code': 'PM7',       'name': 'Pre-Match 7AM',     'start_time': time(7, 0),  'end_time': time(15, 0), 'category': cat_am,  'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#F59E0B'},
            {'code': 'PM9',       'name': 'Pre-Match 9AM',     'start_time': time(9, 0),  'end_time': time(17, 0), 'category': cat_ins, 'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#D97706'},
            {'code': 'NS',        'name': 'Night Shift',       'start_time': time(22, 0), 'end_time': time(6, 0),  'category': cat_ns,  'applicable_to_monitor': True,  'applicable_to_inplay': True,  'color_code': '#6366F1'},
            {'code': 'HO-IP6',    'name': 'Home Office 6AM',   'start_time': time(6, 0),  'end_time': time(14, 0), 'category': cat_ho,  'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#8B5CF6'},
            {'code': 'HO-IP10',   'name': 'Home Office 10AM',  'start_time': time(10, 0), 'end_time': time(18, 0), 'category': cat_ho,  'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#7C3AED'},
            {'code': 'HO-IP12',   'name': 'Home Office 12PM',  'start_time': time(12, 0), 'end_time': time(20, 0), 'category': cat_ho,  'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#6D28D9'},
            {'code': 'HO-IP14',   'name': 'Home Office 2PM',   'start_time': time(14, 0), 'end_time': time(22, 0), 'category': cat_ho,  'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#5B21B6'},
            {'code': 'IP10-FER14','name': 'Ferdinando 10-14',  'start_time': time(10, 0), 'end_time': time(14, 0), 'category': cat_ins, 'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#EC4899'},
            {'code': 'FERDI10',   'name': 'Ferdinando 10AM',   'start_time': time(10, 0), 'end_time': time(18, 0), 'category': cat_ins, 'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#DB2777'},
            {'code': 'FERDI14',   'name': 'Ferdinando 2PM',    'start_time': time(14, 0), 'end_time': time(22, 0), 'category': cat_mid, 'applicable_to_monitor': False, 'applicable_to_inplay': True,  'color_code': '#BE185D'},
        ]

        # Status codes (is_working_shift=False, no times, no category)
        status_shifts = [
            {'code': 'CUMPLE', 'name': 'Cumpleanos', 'color_code': '#FFD700'},
            {'code': 'OFF',    'name': 'Dia Libre',  'color_code': '#9CA3AF'},
            {'code': 'VAC',    'name': 'Vacaciones',  'color_code': '#3B82F6'},
            {'code': 'FES',    'name': 'Dia Festivo', 'color_code': '#EF4444'},
        ]

        st_created_count = 0

        for shift_data in working_shifts:
            obj, created = ShiftType.objects.get_or_create(
                code=shift_data['code'],
                defaults={
                    'name': shift_data['name'],
                    'category': shift_data['category'],
                    'start_time': shift_data['start_time'],
                    'end_time': shift_data['end_time'],
                    'is_working_shift': True,
                    'color_code': shift_data['color_code'],
                    'applicable_to_monitor': shift_data['applicable_to_monitor'],
                    'applicable_to_inplay': shift_data['applicable_to_inplay'],
                    'is_active': True,
                },
            )
            st_created_count += int(created)
            status = 'CREATED' if created else 'exists'
            self.stdout.write(f'  [{status}] ShiftType: {obj.code} - {obj.name}')

        for shift_data in status_shifts:
            obj, created = ShiftType.objects.get_or_create(
                code=shift_data['code'],
                defaults={
                    'name': shift_data['name'],
                    'category': None,
                    'start_time': None,
                    'end_time': None,
                    'is_working_shift': False,
                    'color_code': shift_data['color_code'],
                    'applicable_to_monitor': True,
                    'applicable_to_inplay': True,
                    'is_active': True,
                },
            )
            st_created_count += int(created)
            status = 'CREATED' if created else 'exists'
            self.stdout.write(f'  [{status}] ShiftType: {obj.code} - {obj.name}')

        # ── 3. Team ──────────────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Team ---'))

        team, team_created = Team.objects.get_or_create(
            name='Equipo Principal',
            defaults={
                'description': 'Equipo principal de traders - Monitor, In-Play y Pre-Match',
                'is_active': True,
            },
        )
        status = 'CREATED' if team_created else 'exists'
        self.stdout.write(f'  [{status}] Team: {team.name}')

        # ── 4. Users + Employees (17 people) ─────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Users & Employees ---'))

        PASSWORD = 'Caliente2026!'

        # (employee_id, username, first_name, last_name, role, is_staff, exclude_from_grid)
        staff = [
            ('EMP-001', 'felix.egana',           'Felix Hiram',       'Egana Luquin',          'ADMIN',          True,  True),
            ('EMP-002', 'ferdinando.castriota',   'Ferdinando',        'Castriota',             'MANAGER',        False, False),
            ('EMP-003', 'manuel.delgado',         'Manuel Alberto',    'Delgado Martinez',      'MANAGER',        False, False),
            ('EMP-004', 'ricardo.moreno',         'Ricardo David',     'Moreno Munoz',          'MONITOR_TRADER', False, False),
            ('EMP-005', 'salvador.moreno',        'Salvador',          'Moreno Acosta',         'MONITOR_TRADER', False, False),
            ('EMP-006', 'jesus.castillo',         'Jesus Arnoldo',     'Castillo Rodriguez',    'MONITOR_TRADER', False, False),
            ('EMP-007', 'gilberto.gonzalez',      'Gilberto Daniel',   'Gonzalez De Leon',      'MONITOR_TRADER', False, False),
            ('EMP-008', 'jorge.duenas',           'Jorge Esteban',     'Duenas Andrade',        'INPLAY_TRADER',  False, False),
            ('EMP-009', 'fabian.ochoa',           'Fabian Ulises',     'Ochoa Orta',            'INPLAY_TRADER',  False, False),
            ('EMP-010', 'rafael.huerta',          'Rafael Alejandro',  'Huerta Vironchi',       'INPLAY_TRADER',  False, False),
            ('EMP-011', 'gilberto.lares',         'Gilberto',          'Lares Flores',          'INPLAY_TRADER',  False, False),
            ('EMP-012', 'david.rodriguez',        'David',             'Rodriguez Zanatta',     'INPLAY_TRADER',  False, False),
            ('EMP-013', 'omar.castro',            'Omar Alexis',       'Castro Yee',            'INPLAY_TRADER',  False, False),
            ('EMP-014', 'andres.alvarado',        'Andres',            'Alvarado Iriarte',      'INPLAY_TRADER',  False, False),
            ('EMP-015', 'alejandro.vizcarra',     'Alejandro',         'Vizcarra Orozco',       'INPLAY_TRADER',  False, False),
            ('EMP-016', 'angel.lucio',            'Angel',             'Lucio Medina',          'INPLAY_TRADER',  False, False),
            ('EMP-017', 'milton.najera',          'Milton Gabriel',    'Najera Coronado',       'INPLAY_TRADER',  False, False),
        ]

        user_created_count = 0
        emp_created_count = 0

        for emp_id, username, first_name, last_name, role, is_staff, exclude_from_grid in staff:
            # Create or retrieve User
            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f'{username}@caliente.mx',
                    'is_staff': is_staff,
                    'is_superuser': False,
                },
            )
            if user_created:
                user.set_password(PASSWORD)
                user.save()

            user_created_count += int(user_created)
            u_status = 'CREATED' if user_created else 'exists'
            self.stdout.write(f'  [{u_status}] User: {user.username} ({user.email})')

            # Create or retrieve Employee
            employee, emp_created = Employee.objects.get_or_create(
                employee_id=emp_id,
                defaults={
                    'user': user,
                    'role': role,
                    'team': team,
                    'is_active': True,
                    'exclude_from_grid': exclude_from_grid,
                },
            )
            emp_created_count += int(emp_created)
            e_status = 'CREATED' if emp_created else 'exists'
            self.stdout.write(f'  [{e_status}] Employee: {employee.employee_id} - {employee.full_name} (role={employee.role})')

        # ── 5. Set Felix as team manager ─────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING('\n--- Team Manager ---'))

        felix_employee = Employee.objects.get(employee_id='EMP-001')
        if not team.manager:
            team.manager = felix_employee
            team.save()
            self.stdout.write(f'  [SET] Team "{team.name}" -> Manager: {felix_employee.full_name}')
        else:
            self.stdout.write(f'  [exists] Team "{team.name}" already has manager: {team.manager.full_name}')

        # ── Summary ──────────────────────────────────────────────────────
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Seed completed successfully ==='))
        self.stdout.write(self.style.SUCCESS(f'  ShiftCategories : {cat_created_count} created / {len(categories_data)} total'))
        self.stdout.write(self.style.SUCCESS(f'  ShiftTypes      : {st_created_count} created / {len(working_shifts) + len(status_shifts)} total'))
        self.stdout.write(self.style.SUCCESS(f'  Teams           : {int(team_created)} created / 1 total'))
        self.stdout.write(self.style.SUCCESS(f'  Users           : {user_created_count} created / {len(staff)} total'))
        self.stdout.write(self.style.SUCCESS(f'  Employees       : {emp_created_count} created / {len(staff)} total'))
        self.stdout.write(self.style.SUCCESS(f'  Password        : {PASSWORD}'))
        self.stdout.write(self.style.SUCCESS(f'  Email pattern   : {{username}}@caliente.mx'))
        self.stdout.write('')
