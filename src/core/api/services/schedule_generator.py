"""
Schedule Generation Algorithm v2.0 — 5-Layer Constraint Engine
==============================================================

Genera horarios mensuales inteligentes con:

Layer 1 — Continuidad Temporal:
    Consulta los ultimos 7 dias del mes anterior para evitar conflictos
    de transicion (ej. NS → AM al cruzar meses).

Layer 2 — Vacaciones Aprobadas (Hard Constraint):
    SOLO vacaciones con status=APPROVED se bloquean como inmutables.
    Solicitudes pendientes se ignoran completamente.

Layer 3 — Demanda por Prioridad (Weighted Demand):
    Lee Eventos y Ligas para identificar dias de alta demanda.
    En esos dias se minimiza OFF y se maximiza cobertura.

Layer 4 — Distribucion Inteligente de OFF (Smart OFFs):
    Limita cuantos traders pueden tener OFF el mismo dia.
    Los OFFs se dan en dias de baja demanda y se escalonan.
    Garantiza que NINGUN trader quede sin asignacion.

Layer 5 — Monitor Trader Rule:
    Exactamente 1 Monitor Trader en AM, 1 en INS, 1 en MID cada dia.

Version: 2.0
"""

import time
import calendar
import math
from datetime import date, timedelta, datetime
from collections import defaultdict

from django.db.models import Q, Sum
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
    Motor de generacion de horarios mensuales v2.0.

    Flujo:
      1. Cargar datos base y construir caches
      2. Layer 1: Leer historial del mes anterior (continuidad)
      3. Layer 2: Bloquear vacaciones APROBADAS (hard lock)
      4. Layer 3: Calcular mapa de demanda por dia
      5. Layer 4 + 5: Asignar dia a dia con smart-OFF + monitor rule
      6. Bulk-save y crear log
    """

    def __init__(self, month, year, user):
        self.month = month
        self.year = year
        self.user = user
        self.warnings = []
        self.errors = []
        self.decisions = []
        self._events_count = 0
        self._run_assignments = {}  # (employee_id, date) → shift_code — in-memory tracker

    # ═══════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════

    def generate(self):
        """Punto de entrada principal. Retorna ScheduleGenerationLog."""
        start_time = time.time()

        try:
            # — Base data —
            settings = SystemSettings.load()
            traders = self._get_active_traders()
            shift_types = self._get_shift_types()
            categories = self._get_categories()
            cycles = self._get_cycle_configs()
            days = self._get_month_days()

            if not traders:
                self.errors.append("No hay traders activos disponibles.")
                return self._create_log(0, start_time, settings)

            # — Build caches —
            st_cache = {st.code: st for st in shift_types}
            cat_min = {cat.code: cat.min_traders for cat in categories}

            # — Separate traders by role —
            monitor_traders = [t for t in traders if t.role == Employee.Role.MONITOR_TRADER]
            inplay_traders = [t for t in traders if t.role == Employee.Role.INPLAY_TRADER]
            prematch_traders = [t for t in traders if t.role == Employee.Role.PREMATCH_TRADER]

            # — Layer 1: Continuidad temporal —
            prior_history = self._load_prior_history(traders, st_cache)

            # — Layer 2: Lock approved vacations —
            locked_cells = self._lock_approved_vacations(traders, days, st_cache)

            # — Preserve existing manual/swap edits —
            self._lock_existing_schedules(traders, days, locked_cells)

            # — DELETE old algorithm schedules to avoid unique constraint conflicts —
            deleted_count, _ = Schedule.objects.filter(
                date__in=days,
                employee__in=[t.id for t in traders],
                edit_source=Schedule.EditSource.ALGORITHM,
            ).delete()
            if deleted_count:
                self.decisions.append(
                    f"CLEANUP: {deleted_count} asignaciones algoritmo previas eliminadas"
                )

            # — Layer 3: Demand map —
            demand_map = self._compute_demand_map(days)

            # — Init tracker state —
            assignment_counts = defaultdict(int)  # fairness: total shifts per trader
            off_counts = defaultdict(int)          # how many OFFs each trader has
            last_shift = {}                        # last assigned shift code per trader

            # Seed from prior history (Layer 1)
            for trader in traders:
                hist = prior_history.get(trader.id, [])
                if hist:
                    last_shift[trader.id] = hist[-1]  # last shift code before this month
                    # Count consecutive working days from prior month tail
                else:
                    last_shift[trader.id] = None

            # Cycle position tracking
            cycle_positions = {t.id: 0 for t in traders}

            # Seed cycle positions from prior history
            for trader in traders:
                hist = prior_history.get(trader.id, [])
                cycle = cycles.get(trader.role, [])
                if hist and cycle:
                    last_code = hist[-1]
                    if last_code in cycle:
                        idx = cycle.index(last_code)
                        cycle_positions[trader.id] = (idx + 1) % len(cycle)

            # — Calculate max OFF per day —
            total_traders = len(traders)
            # Aim for ~1 day off per 6 working days
            target_off_per_trader = max(1, len(days) // 7)
            max_off_per_day = max(1, math.ceil(total_traders * target_off_per_trader / len(days)))

            self.decisions.append(
                f"CONFIG: {total_traders} traders, {len(days)} dias, "
                f"max_off/dia={max_off_per_day}, target_off/trader={target_off_per_trader}"
            )

            # — Layer 4+5: Day-by-day assignment —
            all_assignments = []
            for day in days:
                day_assignments = self._assign_day(
                    day=day,
                    traders=traders,
                    monitor_traders=monitor_traders,
                    inplay_traders=inplay_traders,
                    locked_cells=locked_cells,
                    categories=categories,
                    cat_min=cat_min,
                    cycles=cycles,
                    settings=settings,
                    st_cache=st_cache,
                    assignment_counts=assignment_counts,
                    off_counts=off_counts,
                    last_shift=last_shift,
                    cycle_positions=cycle_positions,
                    demand_map=demand_map,
                    max_off_per_day=max_off_per_day,
                    target_off_per_trader=target_off_per_trader,
                    total_days=len(days),
                )
                all_assignments.extend(day_assignments)

            # — Bulk save —
            if all_assignments:
                Schedule.objects.bulk_create(all_assignments, ignore_conflicts=True)

            total = len(all_assignments)
            scheduled_traders = len(set(a.employee_id for a in all_assignments))

        except Exception as e:
            self.errors.append(f"Error interno: {str(e)}")
            import traceback
            self.errors.append(traceback.format_exc())
            total = 0
            scheduled_traders = 0
            settings = SystemSettings.load()

        return self._create_log(total, start_time, settings, scheduled_traders)

    # ═══════════════════════════════════════════════════════
    # DATA LOADING
    # ═══════════════════════════════════════════════════════

    def _get_active_traders(self):
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
        return list(
            ShiftType.objects.filter(is_active=True).select_related("category")
        )

    def _get_categories(self):
        return list(ShiftCategory.objects.all().order_by('display_order'))

    def _get_cycle_configs(self):
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
        if Employee.Role.PREMATCH_TRADER not in configs:
            configs[Employee.Role.PREMATCH_TRADER] = [
                "IP6", "IP9", "IP10", "IP12", "IP14", "OFF",
            ]
        return configs

    def _get_month_days(self):
        num_days = calendar.monthrange(self.year, self.month)[1]
        return [date(self.year, self.month, d) for d in range(1, num_days + 1)]

    # ═══════════════════════════════════════════════════════
    # LAYER 1 — CONTINUIDAD TEMPORAL
    # ═══════════════════════════════════════════════════════

    def _load_prior_history(self, traders, st_cache):
        """
        Carga los ultimos 7 dias del mes/periodo anterior.
        Retorna: { employee_id: [shift_code, shift_code, ...] } (cronologico)
        """
        first_day = date(self.year, self.month, 1)
        lookback_start = first_day - timedelta(days=7)
        lookback_end = first_day - timedelta(days=1)

        history = defaultdict(list)
        schedules = (
            Schedule.objects
            .filter(
                employee__in=[t.id for t in traders],
                date__gte=lookback_start,
                date__lte=lookback_end,
            )
            .select_related("shift_type")
            .order_by("date")
        )

        for sched in schedules:
            history[sched.employee_id].append(sched.shift_type.code)

        if history:
            self.decisions.append(
                f"LAYER1 CONTINUITY: {len(history)} traders con historial "
                f"previo ({lookback_start} a {lookback_end})"
            )
        return dict(history)

    # ═══════════════════════════════════════════════════════
    # LAYER 2 — VACACIONES APROBADAS (HARD CONSTRAINT)
    # ═══════════════════════════════════════════════════════

    def _lock_approved_vacations(self, traders, days, st_cache):
        """
        SOLO vacaciones con status='APPROVED' se bloquean.
        Pendientes, rechazadas y canceladas se IGNORAN.
        Retorna: { (employee_id, date): shift_code }
        """
        locked = {}
        vac_shift = st_cache.get("VAC")
        if not vac_shift:
            self.warnings.append("ShiftType 'VAC' no encontrado — no se pueden asignar vacaciones.")
            return locked

        approved_vacations = Vacation.objects.filter(
            employee__in=[t.id for t in traders],
            status=Vacation.Status.APPROVED,     # ← STRICTLY approved only
            start_date__lte=days[-1],
            end_date__gte=days[0],
        ).select_related("employee", "approved_by")

        vac_count = 0
        for vac in approved_vacations:
            approver = vac.approved_by.get_full_name() if vac.approved_by else "?"
            for day in days:
                if vac.start_date <= day <= vac.end_date:
                    locked[(vac.employee_id, day)] = "VAC"
                    vac_count += 1

            self.decisions.append(
                f"LAYER2 VAC LOCK: {vac.employee.full_name} "
                f"({vac.start_date} → {vac.end_date}), "
                f"aprobado por {approver}"
            )

        if vac_count:
            self.decisions.append(f"LAYER2 TOTAL: {vac_count} celdas bloqueadas por vacaciones")

        return locked

    def _lock_existing_schedules(self, traders, days, locked_cells):
        """Preserve manually-edited or swap-edited schedules."""
        existing = (
            Schedule.objects
            .filter(
                date__in=days,
                employee__in=[t.id for t in traders],
            )
            .exclude(edit_source=Schedule.EditSource.ALGORITHM)
            .select_related("shift_type")
        )
        count = 0
        for sched in existing:
            key = (sched.employee_id, sched.date)
            if key not in locked_cells:
                locked_cells[key] = sched.shift_type.code
                count += 1

        if count:
            self.decisions.append(f"EXISTING: {count} celdas manuales/swap preservadas")

    # ═══════════════════════════════════════════════════════
    # LAYER 3 — DEMANDA POR PRIORIDAD (WEIGHTED DEMAND)
    # ═══════════════════════════════════════════════════════

    def _compute_demand_map(self, days):
        """
        Calcula la demanda ponderada por dia basada en eventos deportivos.
        Retorna: { date: demand_weight (float) }

        Dias con eventos de prioridad 1-2 → alta demanda → minimizar OFF
        """
        demand = {day: 0.0 for day in days}

        events = SportEvent.objects.filter(
            date_start__date__lte=days[-1],
        ).filter(
            Q(date_end__date__gte=days[0]) | Q(date_end__isnull=True)
        ).select_related("league")

        self._events_count = events.count()
        high_demand_days = set()

        for event in events:
            event_start = event.date_start.date() if isinstance(event.date_start, datetime) else event.date_start
            event_end = (event.date_end.date() if event.date_end else event_start) if isinstance(event.date_end, (datetime, type(None))) else event.date_end
            if event_end is None:
                event_end = event_start

            weight = event.demand_weight  # 11 - priority

            for day in days:
                if event_start <= day <= event_end:
                    demand[day] += weight
                    if event.priority <= 2:
                        high_demand_days.add(day)

        if high_demand_days:
            sorted_days = sorted(high_demand_days)
            self.decisions.append(
                f"LAYER3 HIGH DEMAND: {len(high_demand_days)} dias con eventos P1/P2: "
                f"{', '.join(d.strftime('%d/%m') for d in sorted_days[:10])}"
                f"{'...' if len(sorted_days) > 10 else ''}"
            )

        if self._events_count:
            self.decisions.append(
                f"LAYER3 EVENTS: {self._events_count} eventos considerados"
            )

        return demand

    # ═══════════════════════════════════════════════════════
    # LAYER 4+5 — DAY ASSIGNMENT ENGINE
    # ═══════════════════════════════════════════════════════

    def _assign_day(
        self, day, traders, monitor_traders, inplay_traders,
        locked_cells, categories, cat_min, cycles, settings, st_cache,
        assignment_counts, off_counts, last_shift, cycle_positions,
        demand_map, max_off_per_day, target_off_per_trader, total_days,
    ):
        """Asigna turnos para un solo dia respetando las 5 capas."""
        assignments = []
        day_coverage = defaultdict(int)
        off_shift = st_cache.get("OFF")
        assigned_traders = set()

        # — Count coverage from locked cells —
        for trader in traders:
            key = (trader.id, day)
            if key in locked_cells:
                code = locked_cells[key]
                st = st_cache.get(code)
                if st and st.is_working_shift and st.category:
                    day_coverage[st.category.code] += 1
                assigned_traders.add(trader.id)

        # — Determine demand level for today —
        day_demand = demand_map.get(day, 0.0)
        is_high_demand = day_demand >= 9  # P1 or P2 events
        is_weekend = day.weekday() >= 5

        # — Adjust max OFF based on demand —
        if is_high_demand:
            effective_max_off = max(1, max_off_per_day // 2)  # Halve OFFs on high-demand
        elif is_weekend and not settings.weekend_scheduling:
            effective_max_off = len(traders)  # Everyone off on weekends if disabled
        else:
            effective_max_off = max_off_per_day

        # — Weekend: assign all OFF if scheduling disabled —
        if not settings.weekend_scheduling and is_weekend:
            for trader in traders:
                if trader.id in assigned_traders:
                    continue
                if off_shift:
                    assignments.append(self._make_schedule(trader, day, off_shift))
                    assignment_counts[trader.id] += 1
                    off_counts[trader.id] += 1
                    last_shift[trader.id] = "OFF"
            return assignments

        # — Collect available traders (not locked) —
        available = []
        for trader in traders:
            if trader.id in assigned_traders:
                continue
            available.append(trader)

        # — Calculate who MUST take OFF today (hard constraints) —
        need_off = set()
        for trader in available:
            # Consecutive days check
            consec = self._get_consecutive_work_days(trader.id, day, locked_cells, last_shift)
            if consec >= settings.max_consecutive_days:
                need_off.add(trader.id)
                continue
            # Rest hours check
            if not self._check_rest_hours(trader.id, day, settings.min_rest_hours, st_cache, last_shift):
                need_off.add(trader.id)

        # — Sort available by fairness (least assigned first) —
        available.sort(key=lambda t: (assignment_counts[t.id], off_counts[t.id]))

        # ───────────────────────────────────────────────────
        # LAYER 5: MONITOR TRADER RULE
        # Exactly 1 Monitor in AM, 1 in INS, 1 in MID
        # ───────────────────────────────────────────────────
        avail_monitors = [t for t in available if t.role == Employee.Role.MONITOR_TRADER]
        monitor_target_cats = ['AM', 'INS', 'MID']

        for cat_code in monitor_target_cats:
            # Check if a monitor is already assigned to this category (from locked)
            already_has_monitor = False
            for trader in monitor_traders:
                key = (trader.id, day)
                if key in locked_cells:
                    code = locked_cells[key]
                    st = st_cache.get(code)
                    if st and st.category and st.category.code == cat_code:
                        already_has_monitor = True
                        break

            if already_has_monitor:
                continue

            # Find a monitor trader to assign (prefer non-tired first)
            assigned_monitor = False
            for pass_num in (1, 2):  # Pass 1: skip tired; Pass 2: include tired
                for trader in list(avail_monitors):
                    if pass_num == 1 and trader.id in need_off:
                        continue  # First pass: skip tired monitors

                    cat_shifts = [
                        st for code, st in st_cache.items()
                        if st.category and st.category.code == cat_code
                        and st.is_working_shift
                        and self._shift_applicable_to_trader(st, trader)
                    ]
                    if not cat_shifts:
                        continue

                    shift = self._pick_shift_from_cycle(trader, cat_shifts, cycles, cycle_positions)
                    if shift:
                        assignments.append(self._make_schedule(trader, day, shift))
                        assignment_counts[trader.id] += 1
                        day_coverage[cat_code] = day_coverage.get(cat_code, 0) + 1
                        last_shift[trader.id] = shift.code
                        assigned_traders.add(trader.id)
                        available.remove(trader)
                        avail_monitors.remove(trader)
                        if trader.id in need_off:
                            need_off.discard(trader.id)  # They worked, reset forced-rest
                        assigned_monitor = True
                        break
                if assigned_monitor:
                    break

            if not assigned_monitor:
                self.decisions.append(
                    f"LAYER5: Sin Monitor Trader disponible para {cat_code} el {day}"
                )

        # ───────────────────────────────────────────────────
        # PHASE 1: Coverage minimums (non-monitor traders)
        # ───────────────────────────────────────────────────
        for cat in categories:
            needed = (cat_min.get(cat.code, 0)) - day_coverage.get(cat.code, 0)
            if needed <= 0:
                continue

            cat_shifts = [
                st for code, st in st_cache.items()
                if st.category and st.category.code == cat.code
                and st.is_working_shift
            ]
            if not cat_shifts:
                continue

            filled = 0
            for trader in list(available):
                if filled >= needed:
                    break
                if trader.id in need_off and not is_high_demand:
                    continue  # Skip tired traders unless high demand

                applicable = [
                    s for s in cat_shifts
                    if self._shift_applicable_to_trader(s, trader)
                ]
                if not applicable:
                    continue

                shift = self._pick_shift_from_cycle(trader, applicable, cycles, cycle_positions)
                if shift:
                    assignments.append(self._make_schedule(trader, day, shift))
                    assignment_counts[trader.id] += 1
                    day_coverage[cat.code] = day_coverage.get(cat.code, 0) + 1
                    last_shift[trader.id] = shift.code
                    assigned_traders.add(trader.id)
                    available.remove(trader)
                    filled += 1

            if filled < needed:
                self.decisions.append(
                    f"COVERAGE: {cat.code} el {day}: "
                    f"necesarios={cat_min.get(cat.code, 0)}, "
                    f"asignados={day_coverage.get(cat.code, 0)}"
                )

        # ───────────────────────────────────────────────────
        # PHASE 2: Assign remaining traders (cycle + smart OFF)
        # ───────────────────────────────────────────────────
        off_today = sum(
            1 for t in traders
            if (t.id, day) in locked_cells and locked_cells[(t.id, day)] == "OFF"
        )

        for trader in list(available):
            # Decide: work or OFF?
            should_off = self._should_assign_off(
                trader_id=trader.id,
                day=day,
                off_today=off_today,
                effective_max_off=effective_max_off,
                off_counts=off_counts,
                target_off_per_trader=target_off_per_trader,
                need_off=need_off,
                is_high_demand=is_high_demand,
                total_days=total_days,
                day_number=(day - date(self.year, self.month, 1)).days + 1,
            )

            if should_off and off_shift:
                assignments.append(self._make_schedule(trader, day, off_shift))
                assignment_counts[trader.id] += 1
                off_counts[trader.id] += 1
                off_today += 1
                last_shift[trader.id] = "OFF"
                assigned_traders.add(trader.id)
            else:
                # Assign a working shift from cycle
                cycle = cycles.get(trader.role, ["OFF"])
                working_shifts_in_cycle = [
                    c for c in cycle if c != "OFF" and c in st_cache
                    and self._shift_applicable_to_trader(st_cache[c], trader)
                ]

                if working_shifts_in_cycle:
                    applicable = [st_cache[c] for c in working_shifts_in_cycle]
                    shift = self._pick_shift_from_cycle(trader, applicable, cycles, cycle_positions)
                    if shift:
                        assignments.append(self._make_schedule(trader, day, shift))
                        assignment_counts[trader.id] += 1
                        last_shift[trader.id] = shift.code
                        if shift.category:
                            day_coverage[shift.category.code] = day_coverage.get(shift.category.code, 0) + 1
                        assigned_traders.add(trader.id)
                    elif off_shift:
                        # Fallback: couldn't find applicable shift
                        assignments.append(self._make_schedule(trader, day, off_shift))
                        assignment_counts[trader.id] += 1
                        off_counts[trader.id] += 1
                        off_today += 1
                        last_shift[trader.id] = "OFF"
                        assigned_traders.add(trader.id)
                elif off_shift:
                    # No working shifts in cycle for this trader
                    assignments.append(self._make_schedule(trader, day, off_shift))
                    assignment_counts[trader.id] += 1
                    off_counts[trader.id] += 1
                    off_today += 1
                    last_shift[trader.id] = "OFF"
                    assigned_traders.add(trader.id)

        # — GUARANTEE: No trader left blank —
        for trader in traders:
            if trader.id not in assigned_traders:
                key = (trader.id, day)
                if key not in locked_cells:
                    if off_shift:
                        assignments.append(self._make_schedule(trader, day, off_shift))
                        assignment_counts[trader.id] += 1
                        off_counts[trader.id] += 1
                        last_shift[trader.id] = "OFF"
                        # Log to decisions (diagnostic) not warnings
                        self.decisions.append(
                            f"FALLBACK: {trader.full_name} → OFF el {day}"
                        )

        return assignments

    # ═══════════════════════════════════════════════════════
    # SMART OFF LOGIC (Layer 4)
    # ═══════════════════════════════════════════════════════

    def _should_assign_off(
        self, trader_id, day, off_today, effective_max_off,
        off_counts, target_off_per_trader, need_off,
        is_high_demand, total_days, day_number,
    ):
        """
        Decide si un trader debe recibir OFF hoy.

        Reglas:
        1. Si necesita descanso obligatorio (max consecutivos) → OFF
        2. Si ya se alcanzo el max OFF por dia → NO OFF
        3. En dias de alta demanda → evitar OFF (a menos que sea obligatorio)
        4. Distribuir OFFs equitativamente: traders con menos OFFs acumulados
           reciben OFF primero, pero solo si van "atrasados" en su cuota
        5. Dispersar: intentar no dar OFF a demasiados el mismo dia
        """
        # 1. Forced rest
        if trader_id in need_off:
            return True

        # 2. Daily cap reached
        if off_today >= effective_max_off:
            return False

        # 3. High demand → no voluntary OFF (forced rest already handled above)
        if is_high_demand:
            return False

        # 4. Fairness: has this trader gotten their fair share of OFFs?
        current_off = off_counts.get(trader_id, 0)
        expected_off_so_far = (target_off_per_trader * day_number) / total_days

        # Give OFF if trader is behind their expected quota
        if current_off < expected_off_so_far - 0.5:
            return True

        return False

    # ═══════════════════════════════════════════════════════
    # CONSTRAINT CHECKERS
    # ═══════════════════════════════════════════════════════

    def _get_consecutive_work_days(self, trader_id, day, locked_cells, last_shift_map):
        """Count how many consecutive working days the trader has before `day`."""
        count = 0
        check = day - timedelta(days=1)
        while count < 10:  # safety limit
            key = (trader_id, check)
            if key in locked_cells:
                code = locked_cells[key]
                if code in ("OFF", "VAC", "FES", "CUMPLE"):
                    break
                count += 1
            elif key in self._run_assignments:
                # Check in-memory assignments from current generation run
                code = self._run_assignments[key]
                if code in ("OFF", "VAC", "FES", "CUMPLE"):
                    break
                count += 1
            else:
                # Fallback: check DB for dates before this generation
                sched = Schedule.objects.filter(
                    employee_id=trader_id, date=check,
                ).select_related("shift_type").first()
                if sched and sched.shift_type.is_working_shift:
                    count += 1
                else:
                    break
            check -= timedelta(days=1)
        return count

    def _check_consecutive(self, trader_id, day, max_consecutive, last_shift_map, locked_cells):
        """True if trader can work this day without exceeding max consecutive."""
        consec = self._get_consecutive_work_days(trader_id, day, locked_cells, last_shift_map)
        return consec < max_consecutive

    def _check_rest_hours(self, trader_id, day, min_rest, st_cache, last_shift_map):
        """True if there are enough rest hours since last shift."""
        yesterday = day - timedelta(days=1)
        run_key = (trader_id, yesterday)

        # Priority 1: check in-memory assignments from current run
        if run_key in self._run_assignments:
            code = self._run_assignments[run_key]
            if code in ("OFF", "VAC", "FES", "CUMPLE"):
                return True
            prev_st = st_cache.get(code)
            if not prev_st or not prev_st.end_time:
                return True
            end_hour = prev_st.end_time.hour
        else:
            # Priority 2: check DB (pre-existing schedules)
            prev_sched = Schedule.objects.filter(
                employee_id=trader_id, date=yesterday,
            ).select_related("shift_type").first()

            if not prev_sched:
                # Priority 3: last_shift_map (for Layer 1 seed from prior month)
                last_code = last_shift_map.get(trader_id)
                if not last_code or last_code in ("OFF", "VAC"):
                    return True
                prev_st = st_cache.get(last_code)
                if not prev_st or not prev_st.end_time:
                    return True
                end_hour = prev_st.end_time.hour
            else:
                if not prev_sched.shift_type.end_time:
                    return True
                end_hour = prev_sched.shift_type.end_time.hour

        earliest_start = 6  # Earliest shift starts at 06:00
        rest = (24 - end_hour) + earliest_start
        return rest >= min_rest

    def _shift_applicable_to_trader(self, shift, trader):
        """Check if shift is applicable to the trader's role."""
        if trader.role == Employee.Role.MONITOR_TRADER:
            return shift.applicable_to_monitor
        if trader.role == Employee.Role.INPLAY_TRADER:
            return shift.applicable_to_inplay
        # PREMATCH and others: fall back to inplay applicability
        return shift.applicable_to_inplay

    def _pick_shift_from_cycle(self, trader, applicable_shifts, cycles, positions):
        """Pick the next shift from the trader's cycle that's in applicable_shifts."""
        cycle = cycles.get(trader.role, [])
        pos = positions.get(trader.id, 0)
        applicable_codes = {s.code for s in applicable_shifts}

        # Search from current position
        for offset in range(len(cycle)):
            code = cycle[(pos + offset) % len(cycle)]
            if code in applicable_codes:
                positions[trader.id] = (pos + offset + 1) % len(cycle)
                return next(s for s in applicable_shifts if s.code == code)

        # Fallback: first applicable
        if applicable_shifts:
            return applicable_shifts[0]
        return None

    def _make_schedule(self, trader, day, shift_type):
        self._run_assignments[(trader.id, day)] = shift_type.code
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

    # ═══════════════════════════════════════════════════════
    # LOG CREATION
    # ═══════════════════════════════════════════════════════

    def _create_log(self, total, start_time, settings, scheduled_traders=0):
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
            algorithm_version="2.0",
            parameters_snapshot={
                "max_consecutive_days": settings.max_consecutive_days,
                "min_rest_hours": settings.min_rest_hours,
                "weekend_scheduling": settings.weekend_scheduling,
                "algorithm": "5-layer-constraint-engine",
            },
        )
        return log
