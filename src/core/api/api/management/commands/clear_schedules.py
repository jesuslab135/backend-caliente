"""
Management command: clear_schedules
====================================
Limpia las tablas relacionadas al grid de horarios:
  - Schedule (asignaciones de turnos)
  - ScheduleGenerationLog (logs del algoritmo)

Uso:
    python manage.py clear_schedules              # Borra todo
    python manage.py clear_schedules --month 3 --year 2026   # Solo ese mes
    python manage.py clear_schedules --algorithm-only         # Solo generados por algoritmo
"""

from django.core.management.base import BaseCommand
from api.models import Schedule, ScheduleGenerationLog


class Command(BaseCommand):
    help = 'Limpia Schedule y ScheduleGenerationLog. Acepta filtros opcionales por mes/ano o por edit_source.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month', type=int, default=None,
            help='Filtrar por mes (1-12). Requiere --year.',
        )
        parser.add_argument(
            '--year', type=int, default=None,
            help='Filtrar por ano (ej. 2026). Requiere --month.',
        )
        parser.add_argument(
            '--algorithm-only', action='store_true', default=False,
            help='Solo borrar asignaciones generadas por el algoritmo (edit_source=ALGORITHM).',
        )
        parser.add_argument(
            '--no-logs', action='store_true', default=False,
            help='No borrar ScheduleGenerationLog, solo Schedule.',
        )

    def handle(self, *args, **options):
        month = options['month']
        year = options['year']
        algo_only = options['algorithm_only']
        skip_logs = options['no_logs']

        # Validar que month y year vengan juntos
        if (month and not year) or (year and not month):
            self.stderr.write(self.style.ERROR('--month y --year deben usarse juntos.'))
            return

        # Construir queryset de Schedule
        qs = Schedule.objects.all()
        label_parts = []

        if month and year:
            qs = qs.filter(date__month=month, date__year=year)
            label_parts.append(f'mes={month}, ano={year}')

        if algo_only:
            qs = qs.filter(edit_source=Schedule.EditSource.ALGORITHM)
            label_parts.append('edit_source=ALGORITHM')

        label = f' ({", ".join(label_parts)})' if label_parts else ''

        # Contar antes de borrar
        schedule_count = qs.count()

        log_qs = ScheduleGenerationLog.objects.all()
        if month and year:
            log_qs = log_qs.filter(month=month, year=year)
        log_count = log_qs.count() if not skip_logs else 0

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n=== CLEAR SCHEDULES{label} ==='
        ))
        self.stdout.write(f'  Schedule:               {schedule_count} registros')
        if not skip_logs:
            self.stdout.write(f'  ScheduleGenerationLog:  {log_count} registros')
        self.stdout.write('')

        if schedule_count == 0 and log_count == 0:
            self.stdout.write(self.style.WARNING('No hay registros que borrar.'))
            return

        # Borrar
        deleted_schedules, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'  -> {deleted_schedules} Schedule eliminados'
        ))

        if not skip_logs and log_count > 0:
            deleted_logs, _ = log_qs.delete()
            self.stdout.write(self.style.SUCCESS(
                f'  -> {deleted_logs} ScheduleGenerationLog eliminados'
            ))

        self.stdout.write(self.style.SUCCESS('\nLimpieza completada.\n'))
