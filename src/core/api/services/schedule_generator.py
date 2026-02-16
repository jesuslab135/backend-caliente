"""
Schedule Generation Algorithm (CSP-inspired)
=============================================

Genera horarios mensuales automaticamente respetando:
  - Hard constraints: vacaciones aprobadas, max dias consecutivos, min descanso
  - Soft constraints: cobertura minima por categoria, distribucion equitativa

Version: 1.0
"""

import time
import calendar
from datetime import date, timedelta
from collections import defaultdict

from django.db.models import Q
from django.utils import timezone

from api.models import (
    Employee,
    Schedule,
    ShiftType,
    ShiftCategory,
    ShiftCycleConfig,
    Vacation,
    SportEvent,
    SystemSettings,
    ScheduleGenerationLog,
)


class ScheduleGenerator:
    """
    Motor de generacion de horarios mensuales.

    Flujo:
      1. Cargar restricciones duras (vacaciones, festivos, limites)
      2. Calcular necesidades de cobertura por categoria/dia
      3. Asignar turnos dia a dia usando greedy + fairness
      4. Registrar resultados en ScheduleGenerationLog
    """

    def __init__(self, month, year, user):
        self.month = month
        self.year = year
        self.user = user
        self.warnings = []
        self.errors = []
        self.decisions = []
        self._events_count = 0

    # --- Public API ---

    def generate(self):
        """
        Punto de entrada principal.
        Retorna un ScheduleGenerationLog con los resultados.
        """
        start_time = time.time()

        try:
            # 1. Cargar datos base
            settings = SystemSettings.load()
            traders = self._get_active_traders()
            shift_types = self._get_shift_types()
            categories = self._get_categories_with_coverage()
            cycles = self._get_cycle_configs()
            days = self._get_month_days()

            if not traders:
                self.errors.append("No hay traders activos disponibles")
                return self._create_log(0, start_time, settings)

            # 2. Cargar restricciones duras + cache de shift types
            st_cache = {st.code: st for st in shift_types}
            locked_cells = self._load_hard_constraints(traders, days, st_cache)

            # 3. Rastrear asignaciones acumuladas por trader (fairness)
            assignment_counts = defaultdict(int)

            # 4. Rastrear posicion en el ciclo por trader
            cycle_positions = {}
            for trader in traders:
                cycle_positions[trader.id] = 0

            # 5. Asignar dia por dia
            all_assignments = []
            for day in days:
                day_assignments = self._assign_day(
                    day, traders, locked_cells, categories,
                    cycles, settings, st_cache,
                    assignment_counts, cycle_positions,
                )
                all_assignments.extend(day_assignments)

            # 6. Guardar en BD
            if all_assignments:
                Schedule.objects.bulk_create(all_assignments, ignore_conflicts=True)

            total = len(all_assignments)
            scheduled_traders = len(set(a.employee_id for a in all_assignments))

        except Exception as e:
            self.errors.append(f"Error interno: {str(e)}")
            total = 0
            scheduled_traders = 0
            settings = SystemSettings.load()

        return self._create_log(total, start_time, settings, scheduled_traders)

    # --- Data Loading ---

    def _get_active_traders(self):
        """Traders activos que participan en el grid."""
        return list(
            Employee.objects.filter(
                is_active=True,
                exclude_from_grid=False,
                role__in=[
                    Employee.Role.MONITOR_TRADER,
                    Employee.Role.INPLAY_TRADER,
                    Employee.Role.PREMATCH_TRADER,
                ],
            ).select_related("user")
        )

    def _get_shift_types(self):
        """Todos los tipos de turno activos."""
        return list(
            ShiftType.objects.filter(is_active=True).select_related("category")
        )

    def _get_categories_with_coverage(self):
        """Categorias que requieren cobertura minima."""
        return list(ShiftCategory.objects.filter(min_traders__gt=0))

    def _get_cycle_configs(self):
        """Ciclos por defecto por rol."""
        configs = {}
        for cfg in ShiftCycleConfig.objects.filter(is_default=True):
            configs[cfg.trader_role] = cfg.shift_order
        # Fallbacks
        if Employee.Role.MONITOR_TRADER not in configs:
            configs[Employee.Role.MONITOR_TRADER] = ["MON6", "MON12", "MON14", "OFF"]
        if Employee.Role.INPLAY_TRADER not in configs:
            configs[Employee.Role.INPLAY_TRADER] = [
                "IP6", "IP9", "IP10", "IP12", "IP14", "OFF",
            ]
        return configs

    def _get_month_days(self):
        """Lista de objetos date para cada dia del mes."""
        num_days = calendar.monthrange(self.year, self.month)[1]
        return [date(self.year, self.month, d) for d in range(1, num_days + 1)]

    # --- Hard Constraints ---

    def _load_hard_constraints(self, traders, days, st_cache):
        """
        Retorna dict: { (employee_id, date): shift_code }
        para celdas que estan bloqueadas (VAC, existentes, etc.)
        """
        locked = {}

        # Vacaciones aprobadas -> VAC
        vac_shift = st_cache.get("VAC")
        if vac_shift:
            for trader in traders:
                approved_vacs = Vacation.objects.filter(
                    employee=trader,
                    status=Vacation.Status.APPROVED,
                    start_date__lte=days[-1],
                    end_date__gte=days[0],
                )
                for vac in approved_vacs:
                    for day in days:
                        if vac.start_date <= day <= vac.end_date:
                            locked[(trader.id, day)] = "VAC"
                            self.decisions.append(
                                f"LOCK VAC: {trader.full_name} el {day}"
                            )

        # Schedules existentes (ediciones manuales previas) -> no sobrescribir
        existing = Schedule.objects.filter(
            date__in=days,
            employee__in=[t.id for t in traders],
        ).select_related("shift_type")
        for sched in existing:
            locked[(sched.employee_id, sched.date)] = sched.shift_type.code

        # Sport events con alta prioridad (>=8) para el mes
        # date_start/date_end are DateTimeFields; use __date for comparison
        events = SportEvent.objects.filter(
            date_start__date__lte=days[-1],
            priority__gte=8,
        ).filter(
            Q(date_end__date__gte=days[0]) | Q(date_end__isnull=True)
        )
        self._events_count = events.count()
        if events.exists():
            self.decisions.append(
                f"EVENTS: {self._events_count} eventos de alta prioridad considerados"
            )

        return locked

    # --- Day Assignment ---

    def _assign_day(
        self, day, traders, locked_cells, categories,
        cycles, settings, st_cache,
        assignment_counts, cycle_positions,
    ):
        """Asigna turnos para un solo dia."""
        assignments = []
        day_coverage = defaultdict(int)

        # Contar cobertura ya existente (locked cells que son working shifts)
        for trader in traders:
            key = (trader.id, day)
            if key in locked_cells:
                code = locked_cells[key]
                st = st_cache.get(code)
                if st and st.is_working_shift and st.category:
                    day_coverage[st.category.code] += 1

        # Determinar traders disponibles (no locked, no max consecutive)
        available = []
        for trader in traders:
            if (trader.id, day) in locked_cells:
                continue
            if not self._check_consecutive(trader, day, settings.max_consecutive_days):
                continue
            if not self._check_rest_hours(trader, day, settings.min_rest_hours, st_cache):
                continue
            available.append(trader)

        # Fines de semana: si no esta habilitado, asignar OFF
        off_shift = st_cache.get("OFF")
        if not settings.weekend_scheduling and day.weekday() >= 5:
            for trader in available:
                if off_shift:
                    assignments.append(self._make_schedule(trader, day, off_shift))
                    assignment_counts[trader.id] += 1
            return assignments

        # Ordenar por fairness: menos asignaciones primero
        available.sort(key=lambda t: assignment_counts[t.id])

        # Fase 1: Cubrir minimos de cobertura
        for cat in categories:
            needed = cat.min_traders - day_coverage.get(cat.code, 0)
            if needed <= 0:
                continue

            # Buscar shift types de esta categoria
            cat_shifts = [
                st for code, st in st_cache.items()
                if st.category and st.category.code == cat.code
                and st.is_working_shift
            ]
            if not cat_shifts:
                self.warnings.append(
                    f"Sin turnos activos para categoria {cat.code} el {day}"
                )
                continue

            filled = 0
            for trader in list(available):
                if filled >= needed:
                    break
                # Verificar que el rol del trader permite este shift
                applicable = [
                    s for s in cat_shifts
                    if self._shift_applicable_to_trader(s, trader)
                ]
                if not applicable:
                    continue

                # Elegir turno segun ciclo
                shift = self._pick_shift_from_cycle(
                    trader, applicable, cycles, cycle_positions,
                )
                if shift:
                    assignments.append(self._make_schedule(trader, day, shift))
                    assignment_counts[trader.id] += 1
                    day_coverage[cat.code] = day_coverage.get(cat.code, 0) + 1
                    available.remove(trader)
                    filled += 1

            if filled < needed:
                self.warnings.append(
                    f"Cobertura insuficiente {cat.code} el {day}: "
                    f"necesarios={cat.min_traders}, asignados={day_coverage.get(cat.code, 0)}"
                )

        # Fase 2: Asignar turnos a traders restantes usando su ciclo
        for trader in available:
            cycle = cycles.get(trader.role, ["OFF"])
            pos = cycle_positions.get(trader.id, 0)
            code = cycle[pos % len(cycle)]
            shift = st_cache.get(code)
            if not shift:
                shift = off_shift
            if shift:
                assignments.append(self._make_schedule(trader, day, shift))
                assignment_counts[trader.id] += 1
                cycle_positions[trader.id] = (pos + 1) % len(cycle)

        return assignments

    # --- Helpers ---

    def _check_consecutive(self, trader, day, max_consecutive):
        """
        Retorna True si el trader puede trabajar este dia sin
        exceder max_consecutive dias consecutivos.
        """
        consecutive = 0
        check_date = day - timedelta(days=1)
        while consecutive < max_consecutive:
            has_work = Schedule.objects.filter(
                employee=trader,
                date=check_date,
                shift_type__is_working_shift=True,
            ).exists()
            if not has_work:
                break
            consecutive += 1
            check_date -= timedelta(days=1)
        return consecutive < max_consecutive

    def _check_rest_hours(self, trader, day, min_rest, st_cache):
        """
        Retorna True si hay suficiente descanso desde el turno anterior.
        """
        yesterday = day - timedelta(days=1)
        prev = Schedule.objects.filter(
            employee=trader, date=yesterday,
        ).select_related("shift_type").first()
        if not prev or not prev.shift_type.end_time:
            return True
        # Comparar end_time de ayer con 06:00 (turno mas temprano)
        end_hour = prev.shift_type.end_time.hour
        earliest_start = 6
        rest = (24 - end_hour) + earliest_start
        return rest >= min_rest

    def _shift_applicable_to_trader(self, shift, trader):
        """Verifica que el turno sea aplicable al rol del trader."""
        if trader.role == Employee.Role.MONITOR_TRADER:
            return shift.applicable_to_monitor
        if trader.role == Employee.Role.INPLAY_TRADER:
            return shift.applicable_to_inplay
        return shift.applicable_to_monitor  # fallback for PREMATCH

    def _pick_shift_from_cycle(self, trader, applicable_shifts, cycles, positions):
        """
        Elige un turno de la lista que mejor siga el ciclo del trader.
        """
        cycle = cycles.get(trader.role, [])
        pos = positions.get(trader.id, 0)
        applicable_codes = {s.code for s in applicable_shifts}

        # Buscar desde la posicion actual en el ciclo
        for offset in range(len(cycle)):
            code = cycle[(pos + offset) % len(cycle)]
            if code in applicable_codes:
                positions[trader.id] = (pos + offset + 1) % len(cycle)
                return next(s for s in applicable_shifts if s.code == code)

        # Si ninguno del ciclo encaja, tomar el primero disponible
        if applicable_shifts:
            return applicable_shifts[0]
        return None

    def _make_schedule(self, trader, day, shift_type):
        """Crea un objeto Schedule (sin guardar aun)."""
        return Schedule(
            employee=trader,
            shift_type=shift_type,
            date=day,
            title=f"{shift_type.code} - {trader.full_name}",
            edit_source=Schedule.EditSource.ALGORITHM,
            created_by=self.user,
            last_edited_by=self.user,
            last_edited_at=timezone.now(),
        )

    # --- Logging ---

    def _create_log(self, total, start_time, settings, scheduled_traders=0):
        """Crea el registro de log de generacion."""
        execution_time = time.time() - start_time
        status = ScheduleGenerationLog.Status.SUCCESS
        if self.errors:
            status = ScheduleGenerationLog.Status.FAILED
        elif self.warnings:
            status = ScheduleGenerationLog.Status.PARTIAL

        log = ScheduleGenerationLog.objects.create(
            month=self.month,
            year=self.year,
            generated_by=self.user,
            status=status,
            total_assignments=total,
            events_considered=self._events_count,
            traders_scheduled=scheduled_traders,
            warnings=self.warnings,
            errors=self.errors,
            algorithm_decisions=self.decisions[:100],
            execution_time_seconds=round(execution_time, 2),
            algorithm_version=settings.default_algorithm_version,
            parameters_snapshot={
                "max_consecutive_days": settings.max_consecutive_days,
                "min_rest_hours": settings.min_rest_hours,
                "weekend_scheduling": settings.weekend_scheduling,
            },
        )
        return log
