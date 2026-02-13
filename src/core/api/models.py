"""
Enterprise Scheduler System - Models
=====================================

Modelos de Django ORM para el sistema de gestión y automatización de horarios.
Diseñado para operaciones de trading deportivo (Caliente Traders).

Versión: 1.1
Basado en: SRS Enterprise Scheduler System v1.1

Convenciones:
- Todos los modelos incluyen campos de auditoría (created_at, updated_at)
- Se usan UUIDs para IDs públicos expuestos en API (seguridad)
- Los campos de filtrado frecuente tienen db_index=True
- related_name explícitos para facilitar queries inversas en DRF serializers
"""

import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
    RegexValidator,
)
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# =============================================================================
# VALIDATORS - Validadores personalizados reutilizables
# =============================================================================

def validate_hex_color(value):
    """
    Valida que el valor sea un código de color hexadecimal válido.
    Formato esperado: #RRGGBB o #RGB
    """
    import re
    if not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', value):
        raise ValidationError(
            _('%(value)s no es un código de color hexadecimal válido. Use formato #RRGGBB'),
            params={'value': value},
        )


def validate_shift_order(value):
    """
    Valida que shift_order sea una lista de strings (códigos de turno).
    """
    if not isinstance(value, list):
        raise ValidationError(_('shift_order debe ser una lista'))
    if not all(isinstance(item, str) for item in value):
        raise ValidationError(_('Todos los elementos de shift_order deben ser strings'))
    if len(value) < 2:
        raise ValidationError(_('shift_order debe tener al menos 2 elementos'))


# =============================================================================
# ABSTRACT BASE MODELS - Modelos base reutilizables
# =============================================================================

class TimeStampedModel(models.Model):
    """
    Modelo abstracto que proporciona campos de auditoría temporal.
    Todos los modelos del sistema heredan de este para consistencia.
    """
    created_at = models.DateTimeField(
        _('fecha de creación'),
        auto_now_add=True,
        help_text=_('Fecha y hora de creación del registro')
    )
    updated_at = models.DateTimeField(
        _('fecha de actualización'),
        auto_now=True,
        help_text=_('Fecha y hora de última modificación')
    )

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """
    Modelo abstracto que proporciona un UUID público.
    Útil para exponer IDs en API sin revelar IDs secuenciales internos.
    
    Decisión de diseño: Mantenemos el AutoField como PK interno por rendimiento
    en JOINs, pero exponemos el UUID en la API por seguridad.
    """
    uuid = models.UUIDField(
        _('identificador único'),
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text=_('Identificador único público para uso en API')
    )

    class Meta:
        abstract = True


# =============================================================================
# TEAM - Equipos de trabajo
# =============================================================================

class Team(TimeStampedModel, UUIDModel):
    """
    Representa un equipo de trabajo dentro de la organización.
    
    Los equipos agrupan traders para facilitar la gestión de horarios
    y la asignación de supervisores/managers.
    
    Nota: El campo 'manager' es nullable para permitir crear equipos
    antes de asignar un líder (chicken-egg problem con Employee).
    """
    name = models.CharField(
        _('nombre del equipo'),
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_('Nombre único del equipo')
    )
    description = models.TextField(
        _('descripción'),
        blank=True,
        default='',
        help_text=_('Descripción opcional del equipo y sus responsabilidades')
    )
    is_active = models.BooleanField(
        _('activo'),
        default=True,
        db_index=True,
        help_text=_('Indica si el equipo está activo en el sistema')
    )
    # manager se define después de Employee para evitar dependencia circular

    class Meta:
        verbose_name = _('equipo')
        verbose_name_plural = _('equipos')
        ordering = ['name']

    def __str__(self):
        status = '' if self.is_active else ' [INACTIVO]'
        return f"{self.name}{status}"

    def get_active_members_count(self):
        """Retorna el número de miembros activos del equipo."""
        return self.employees.filter(is_active=True).count()


# =============================================================================
# EMPLOYEE - Perfil extendido de usuario (Trader/Manager/Admin)
# =============================================================================

class Employee(TimeStampedModel, UUIDModel):
    """
    Perfil extendido del usuario Django para el sistema de scheduling.
    
    Representa a un trader (Monitor o In-Play), supervisor o administrador.
    Se relaciona 1:1 con el modelo User de Django para aprovechar el sistema
    de autenticación y permisos nativo.
    
    Decisión de diseño: Usamos OneToOneField en lugar de heredar de AbstractUser
    para mantener la flexibilidad y no acoplar fuertemente con el modelo User.
    """
    
    class Role(models.TextChoices):
        """Roles disponibles para empleados."""
        MONITOR_TRADER = 'MONITOR_TRADER', _('Monitor Trader')
        INPLAY_TRADER = 'INPLAY_TRADER', _('In-Play Trader')
        PREMATCH_TRADER = 'PREMATCH_TRADER', _('Pre-Match Trader')
        MANAGER = 'MANAGER', _('Manager/Supervisor')
        ADMIN = 'ADMIN', _('Administrador')
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,  # Si se elimina el User, se elimina el Employee
        related_name='employee_profile',
        verbose_name=_('usuario'),
        help_text=_('Usuario Django asociado a este empleado')
    )
    employee_id = models.CharField(
        _('código de empleado'),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_('Código interno único del empleado (ej: EMP-001)')
    )
    phone = models.CharField(
        _('teléfono'),
        max_length=20,
        blank=True,
        default='',
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message=_('Formato de teléfono inválido. Use formato internacional.')
            )
        ],
        help_text=_('Número de teléfono para notificaciones WhatsApp')
    )
    role = models.CharField(
        _('rol'),
        max_length=20,
        choices=Role.choices,
        default=Role.MONITOR_TRADER,
        db_index=True,
        help_text=_('Rol del empleado en la organización')
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,  # Si se elimina el equipo, el empleado queda sin equipo
        null=True,
        blank=True,
        related_name='employees',
        verbose_name=_('equipo'),
        help_text=_('Equipo al que pertenece el empleado')
    )
    is_active = models.BooleanField(
        _('activo'),
        default=True,
        db_index=True,
        help_text=_('Indica si el empleado está activo. Usar para soft delete.')
    )
    exclude_from_grid = models.BooleanField(
        _('excluir de grilla'),
        default=False,
        help_text=_('Si es True, el empleado no aparece en la grilla de horarios')
    )
    hire_date = models.DateField(
        _('fecha de contratación'),
        null=True,
        blank=True,
        help_text=_('Fecha en que el empleado fue contratado')
    )
    # Preferencias de turno (soft constraint para el algoritmo)
    preferred_shift_category = models.ForeignKey(
        'ShiftCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preferred_by_employees',
        verbose_name=_('categoría de turno preferida'),
        help_text=_('Preferencia de turno del empleado (considerado como soft constraint)')
    )

    class Meta:
        verbose_name = _('empleado')
        verbose_name_plural = _('empleados')
        ordering = ['employee_id']
        indexes = [
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['team', 'is_active']),
        ]

    def __str__(self):
        return f"{self.employee_id} - {self.user.get_full_name() or self.user.username}"

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        # Un manager no puede ser su propio supervisor de equipo
        if self.team and self.team.manager_id == self.pk:
            if self.role != Employee.Role.MANAGER:
                raise ValidationError(
                    _('El líder de un equipo debe tener rol de Manager')
                )

    @property
    def full_name(self):
        """Nombre completo del empleado."""
        return self.user.get_full_name() or self.user.username

    @property
    def email(self):
        """Email del empleado (delegado al User)."""
        return self.user.email

    def is_available_on_date(self, date):
        """
        Verifica si el empleado está disponible en una fecha específica.
        Considera vacaciones aprobadas.
        """
        return not self.vacations.filter(
            status=Vacation.Status.APPROVED,
            start_date__lte=date,
            end_date__gte=date
        ).exists()


# Añadir el campo manager a Team después de definir Employee
Team.add_to_class(
    'manager',
    models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_teams',
        verbose_name=_('manager'),
        help_text=_('Empleado que lidera este equipo')
    )
)


# =============================================================================
# SHIFT CATEGORY - Categorías de turno (AM, INS, MID, NS)
# =============================================================================

class ShiftCategory(TimeStampedModel):
    """
    Categoría de turno que agrupa múltiples tipos de turno.
    
    Las categorías definen los requisitos mínimos de cobertura.
    Según el SRS:
    - AM: Mínimo 3 traders (6AM-2PM)
    - INS: Mínimo 0 traders (9AM-6PM) - Turno swing
    - MID: Mínimo 3 traders (2PM-10PM)
    - NS: Mínimo 1 trader (10PM-6AM)
    
    Decisión de diseño: Usamos PositiveSmallIntegerField para min_traders
    porque es un valor pequeño y ahorra espacio en BD.
    """
    code = models.CharField(
        _('código'),
        max_length=10,
        unique=True,
        db_index=True,
        help_text=_('Código único de la categoría (ej: AM, INS, MID, NS)')
    )
    name = models.CharField(
        _('nombre'),
        max_length=50,
        help_text=_('Nombre descriptivo de la categoría')
    )
    min_traders = models.PositiveSmallIntegerField(
        _('mínimo de traders'),
        default=0,
        validators=[MaxValueValidator(50)],
        help_text=_('Número mínimo de traders requeridos para esta categoría')
    )
    description = models.TextField(
        _('descripción'),
        blank=True,
        default='',
        help_text=_('Descripción detallada del turno')
    )
    # Horario aproximado de referencia (no restrictivo, solo informativo)
    typical_start_time = models.TimeField(
        _('hora típica de inicio'),
        null=True,
        blank=True,
        help_text=_('Hora aproximada de inicio de turnos en esta categoría')
    )
    typical_end_time = models.TimeField(
        _('hora típica de fin'),
        null=True,
        blank=True,
        help_text=_('Hora aproximada de fin de turnos en esta categoría')
    )
    display_order = models.PositiveSmallIntegerField(
        _('orden de visualización'),
        default=0,
        help_text=_('Orden para mostrar en interfaces de usuario')
    )

    class Meta:
        verbose_name = _('categoría de turno')
        verbose_name_plural = _('categorías de turno')
        ordering = ['display_order', 'code']

    def __str__(self):
        return f"{self.code} - {self.name} (min: {self.min_traders})"


# =============================================================================
# SHIFT TYPE - Tipos de turno específicos (MON6, IP9, OFF, VAC, etc.)
# =============================================================================

class ShiftType(TimeStampedModel):
    """
    Tipo de turno específico que puede asignarse a un empleado.
    
    Ejemplos según el SRS:
    - MON6: Monitor Trader 6AM-2PM
    - IP9: In-Play Trader 9AM-5PM
    - OFF: Día libre
    - VAC: Vacaciones
    
    Los tipos de turno pertenecen a una categoría (excepto OFF/VAC que son
    turnos no operativos).
    """
    code = models.CharField(
        _('código'),
        max_length=10,
        unique=True,
        db_index=True,
        help_text=_('Código único del tipo de turno (ej: MON6, IP9, OFF)')
    )
    name = models.CharField(
        _('nombre'),
        max_length=100,
        help_text=_('Nombre completo del tipo de turno')
    )
    category = models.ForeignKey(
        ShiftCategory,
        on_delete=models.PROTECT,  # No permitir eliminar categoría si tiene tipos
        null=True,
        blank=True,
        related_name='shift_types',
        verbose_name=_('categoría'),
        help_text=_('Categoría a la que pertenece (null para OFF/VAC)')
    )
    start_time = models.TimeField(
        _('hora de inicio'),
        null=True,
        blank=True,
        help_text=_('Hora de inicio del turno (null para OFF/VAC)')
    )
    end_time = models.TimeField(
        _('hora de fin'),
        null=True,
        blank=True,
        help_text=_('Hora de fin del turno (null para OFF/VAC)')
    )
    is_working_shift = models.BooleanField(
        _('es turno laboral'),
        default=True,
        db_index=True,
        help_text=_('False para turnos no operativos como OFF y VAC')
    )
    color_code = models.CharField(
        _('código de color'),
        max_length=7,
        default='#6B7280',
        validators=[validate_hex_color],
        help_text=_('Color hexadecimal para mostrar en UI (ej: #FF5733)')
    )
    # Para el algoritmo: indica si este tipo aplica a ciertos roles
    applicable_to_monitor = models.BooleanField(
        _('aplicable a Monitor Trader'),
        default=True,
        help_text=_('Si este turno puede asignarse a Monitor Traders')
    )
    applicable_to_inplay = models.BooleanField(
        _('aplicable a In-Play Trader'),
        default=True,
        help_text=_('Si este turno puede asignarse a In-Play Traders')
    )
    is_active = models.BooleanField(
        _('activo'),
        default=True,
        db_index=True,
        help_text=_('Si este tipo de turno está disponible para asignación')
    )

    class Meta:
        verbose_name = _('tipo de turno')
        verbose_name_plural = _('tipos de turno')
        ordering = ['category__display_order', 'start_time', 'code']
        indexes = [
            models.Index(fields=['is_working_shift', 'is_active']),
        ]

    def __str__(self):
        if self.start_time and self.end_time:
            return f"{self.code} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"
        return self.code

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        if self.is_working_shift:
            if not self.start_time or not self.end_time:
                raise ValidationError(
                    _('Los turnos laborales deben tener hora de inicio y fin')
                )
            if not self.category:
                raise ValidationError(
                    _('Los turnos laborales deben pertenecer a una categoría')
                )

    @property
    def duration_hours(self):
        """Calcula la duración del turno en horas."""
        if not self.start_time or not self.end_time:
            return None
        from datetime import datetime, timedelta
        start = datetime.combine(datetime.min, self.start_time)
        end = datetime.combine(datetime.min, self.end_time)
        if end < start:  # Turno nocturno que cruza medianoche
            end += timedelta(days=1)
        return (end - start).seconds / 3600


# =============================================================================
# SHIFT CYCLE CONFIG - Configuración del ciclo de edición grid
# =============================================================================

class ShiftCycleConfig(TimeStampedModel):
    """
    Configuración del orden de ciclo de turnos para la edición in-place del grid.
    
    Cuando un usuario hace clic en una celda del grid de horarios, el turno
    cicla al siguiente en la secuencia definida aquí.
    
    Ejemplo para Monitor Trader: MON6 → MON12 → MON14 → OFF → MON6...
    
    Decisión de diseño: Usamos JSONField para shift_order porque:
    1. La lista es pequeña y ordenada
    2. No necesitamos queries complejas sobre los elementos individuales
    3. Simplifica la lógica de ciclo en el frontend y backend
    """
    name = models.CharField(
        _('nombre'),
        max_length=50,
        unique=True,
        help_text=_('Nombre descriptivo de la configuración (ej: "Ciclo Monitor")')
    )
    trader_role = models.CharField(
        _('rol de trader'),
        max_length=20,
        choices=Employee.Role.choices,
        db_index=True,
        help_text=_('Rol de trader al que aplica esta configuración')
    )
    shift_order = models.JSONField(
        _('orden de ciclo'),
        validators=[validate_shift_order],
        help_text=_('Lista ordenada de códigos de turno ["MON6", "MON12", "OFF"]')
    )
    is_default = models.BooleanField(
        _('es configuración por defecto'),
        default=False,
        help_text=_('Si es la configuración por defecto para el rol')
    )
    include_off = models.BooleanField(
        _('incluir OFF en ciclo'),
        default=True,
        help_text=_('Si el ciclo incluye el código OFF (día libre)')
    )
    include_vac = models.BooleanField(
        _('incluir VAC en ciclo'),
        default=False,
        help_text=_('Si el ciclo incluye el código VAC (vacaciones)')
    )

    class Meta:
        verbose_name = _('configuración de ciclo')
        verbose_name_plural = _('configuraciones de ciclo')
        ordering = ['trader_role', 'name']
        constraints = [
            # Solo puede haber un default por rol
            models.UniqueConstraint(
                fields=['trader_role'],
                condition=models.Q(is_default=True),
                name='unique_default_per_role'
            )
        ]

    def __str__(self):
        default_marker = ' [DEFAULT]' if self.is_default else ''
        return f"{self.name} ({self.get_trader_role_display()}){default_marker}"

    def get_next_shift_code(self, current_code):
        """
        Retorna el siguiente código de turno en el ciclo.
        
        Args:
            current_code: Código actual del turno
            
        Returns:
            Siguiente código en el ciclo, o el primero si current_code no está
        """
        try:
            current_index = self.shift_order.index(current_code)
            next_index = (current_index + 1) % len(self.shift_order)
            return self.shift_order[next_index]
        except ValueError:
            return self.shift_order[0] if self.shift_order else None

    def get_previous_shift_code(self, current_code):
        """
        Retorna el código de turno anterior en el ciclo (Shift+Click).
        """
        try:
            current_index = self.shift_order.index(current_code)
            prev_index = (current_index - 1) % len(self.shift_order)
            return self.shift_order[prev_index]
        except ValueError:
            return self.shift_order[-1] if self.shift_order else None


# =============================================================================
# LEAGUE - Ligas deportivas
# =============================================================================

class League(TimeStampedModel, UUIDModel):
    """
    Representa una liga deportiva cuyos eventos afectan la demanda de traders.
    
    Las ligas agrupan eventos deportivos y permiten categorizar la importancia
    de los mismos para el algoritmo de generación de horarios.
    """
    name = models.CharField(
        _('nombre'),
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_('Nombre de la liga (ej: NFL, NBA, Liga MX)')
    )
    sport = models.CharField(
        _('deporte'),
        max_length=50,
        db_index=True,
        help_text=_('Tipo de deporte (ej: Fútbol Americano, Basketball)')
    )
    country = models.CharField(
        _('país'),
        max_length=50,
        blank=True,
        default='',
        help_text=_('País de origen de la liga')
    )
    is_active = models.BooleanField(
        _('activa'),
        default=True,
        db_index=True,
        help_text=_('Si la liga está activa y se consideran sus eventos')
    )
    # Prioridad base de la liga (afecta el peso de sus eventos)
    base_priority = models.PositiveSmallIntegerField(
        _('prioridad base'),
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_('Prioridad base de la liga (1=máxima, 10=mínima)')
    )

    class Meta:
        verbose_name = _('liga')
        verbose_name_plural = _('ligas')
        ordering = ['base_priority', 'name']

    def __str__(self):
        return f"{self.name} ({self.sport})"


# =============================================================================
# SPORT EVENT - Eventos deportivos
# =============================================================================

class SportEvent(TimeStampedModel, UUIDModel):
    """
    Evento deportivo que determina la demanda de traders.
    
    Los eventos son el input principal del algoritmo de generación.
    La prioridad del evento (1=máxima) determina cuántos traders adicionales
    se necesitan durante ese período.
    
    Fórmula de demanda según SRS:
    Demanda(día) = Σ (11 - prioridad) para cada evento del día
    """
    name = models.CharField(
        _('nombre'),
        max_length=200,
        help_text=_('Nombre del evento (ej: "Super Bowl LVIII")')
    )
    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,  # Si se elimina la liga, se eliminan sus eventos
        related_name='events',
        verbose_name=_('liga'),
        help_text=_('Liga a la que pertenece el evento')
    )
    date_start = models.DateTimeField(
        _('fecha/hora de inicio'),
        db_index=True,
        help_text=_('Fecha y hora de inicio del evento')
    )
    date_end = models.DateTimeField(
        _('fecha/hora de fin'),
        null=True,
        blank=True,
        help_text=_('Fecha y hora de fin del evento (opcional)')
    )
    priority = models.PositiveSmallIntegerField(
        _('prioridad'),
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        db_index=True,
        help_text=_('Prioridad del evento (1=máxima, 10=mínima)')
    )
    description = models.TextField(
        _('descripción'),
        blank=True,
        default='',
        help_text=_('Notas adicionales sobre el evento')
    )
    external_id = models.CharField(
        _('ID externo'),
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        help_text=_('ID del sistema externo para sincronización')
    )

    class Meta:
        verbose_name = _('evento deportivo')
        verbose_name_plural = _('eventos deportivos')
        ordering = ['-date_start', '-priority']
        indexes = [
            models.Index(fields=['date_start', 'priority']),
            models.Index(fields=['league', 'date_start']),
        ]

    def __str__(self):
        return f"{self.name} ({self.date_start.strftime('%Y-%m-%d %H:%M')})"

    def clean(self):
        """Validaciones a nivel de modelo."""
        super().clean()
        if self.date_end and self.date_end < self.date_start:
            raise ValidationError(
                _('La fecha de fin no puede ser anterior a la fecha de inicio')
            )

    @property
    def demand_weight(self):
        """
        Calcula el peso de demanda del evento para el algoritmo.
        Fórmula: 11 - prioridad (prioridad 1 = peso 10)
        """
        return 11 - self.priority

    @property
    def duration_hours(self):
        """Duración estimada del evento en horas."""
        if not self.date_end:
            return 3.0  # Duración default si no se especifica fin
        return (self.date_end - self.date_start).total_seconds() / 3600


# =============================================================================
# SCHEDULE - Asignaciones de turno
# =============================================================================

class Schedule(TimeStampedModel, UUIDModel):
    """
    Asignación de un turno a un empleado en una fecha específica.
    
    Este es el modelo central del sistema. Cada registro representa
    qué turno trabaja un empleado en un día determinado.
    
    Características según SRS v1.1:
    - Constraint único: un empleado solo puede tener una asignación por día
    - Soporte para edición grid in-place con historial de cambios
    - Tracking de origen (algoritmo vs manual vs importación)
    
    Decisión de diseño: Usamos JSONField para edit_history en lugar de una
    tabla separada porque:
    1. Las consultas sobre historial son infrecuentes
    2. Simplifica el modelo y reduce JOINs
    3. El historial por celda es relativamente pequeño
    """
    
    class EditSource(models.TextChoices):
        """Origen de la asignación/edición."""
        ALGORITHM = 'ALGORITHM', _('Generación automática')
        GRID_EDIT = 'GRID_EDIT', _('Edición en grid')
        BULK_IMPORT = 'BULK_IMPORT', _('Importación masiva')
        SWAP = 'SWAP', _('Intercambio de turno')
        MANUAL = 'MANUAL', _('Creación manual')
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='schedules',
        verbose_name=_('empleado'),
        help_text=_('Empleado asignado a este turno')
    )
    shift_type = models.ForeignKey(
        ShiftType,
        on_delete=models.PROTECT,  # No permitir eliminar tipo si tiene asignaciones
        related_name='schedules',
        verbose_name=_('tipo de turno'),
        help_text=_('Tipo de turno asignado')
    )
    date = models.DateField(
        _('fecha'),
        db_index=True,
        help_text=_('Fecha de la asignación')
    )
    # Campos calculados para facilitar queries de disponibilidad
    start_datetime = models.DateTimeField(
        _('inicio'),
        null=True,
        blank=True,
        help_text=_('Fecha/hora de inicio calculada')
    )
    end_datetime = models.DateTimeField(
        _('fin'),
        null=True,
        blank=True,
        help_text=_('Fecha/hora de fin calculada')
    )
    title = models.CharField(
        _('título'),
        max_length=100,
        blank=True,
        default='',
        help_text=_('Título personalizado opcional')
    )
    description = models.TextField(
        _('descripción'),
        blank=True,
        default='',
        help_text=_('Notas adicionales de la asignación')
    )
    # Tracking de origen y ediciones
    edit_source = models.CharField(
        _('origen'),
        max_length=20,
        choices=EditSource.choices,
        default=EditSource.MANUAL,
        db_index=True,
        help_text=_('Cómo fue creada/modificada esta asignación')
    )
    edit_history = models.JSONField(
        _('historial de cambios'),
        default=list,
        blank=True,
        help_text=_('Historial de ediciones [{timestamp, user_id, from_code, to_code}]')
    )
    last_edited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_edits',
        verbose_name=_('última edición por'),
        help_text=_('Usuario que realizó la última edición')
    )
    last_edited_at = models.DateTimeField(
        _('fecha de última edición'),
        null=True,
        blank=True,
        help_text=_('Timestamp de la última edición en grid')
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedules_created',
        verbose_name=_('creado por'),
        help_text=_('Usuario que creó la asignación')
    )

    class Meta:
        verbose_name = _('asignación de turno')
        verbose_name_plural = _('asignaciones de turno')
        ordering = ['date', 'employee__employee_id']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'date'],
                name='unique_employee_date'
            )
        ]
        indexes = [
            models.Index(fields=['date', 'shift_type']),
            models.Index(fields=['employee', 'date']),
            models.Index(fields=['date', 'edit_source']),
        ]

    def __str__(self):
        return f"{self.employee.employee_id} - {self.shift_type.code} ({self.date})"

    def save(self, *args, **kwargs):
        """Override save para calcular campos derivados."""
        self._calculate_datetimes()
        super().save(*args, **kwargs)

    def _calculate_datetimes(self):
        """Calcula start_datetime y end_datetime basado en shift_type."""
        from datetime import datetime, timedelta
        
        if self.shift_type.start_time and self.shift_type.end_time:
            self.start_datetime = datetime.combine(self.date, self.shift_type.start_time)
            self.end_datetime = datetime.combine(self.date, self.shift_type.end_time)
            # Manejar turnos nocturnos que cruzan medianoche
            if self.end_datetime <= self.start_datetime:
                self.end_datetime += timedelta(days=1)
        else:
            self.start_datetime = None
            self.end_datetime = None

    def add_edit_history(self, user, from_code, to_code):
        """
        Añade una entrada al historial de ediciones.
        
        Args:
            user: Usuario que realizó el cambio
            from_code: Código del turno anterior
            to_code: Código del nuevo turno
        """
        entry = {
            'timestamp': timezone.now().isoformat(),
            'user_id': user.id if user else None,
            'user_name': user.get_full_name() if user else 'Sistema',
            'from_code': from_code,
            'to_code': to_code,
        }
        if not isinstance(self.edit_history, list):
            self.edit_history = []
        self.edit_history.append(entry)
        self.last_edited_by = user
        self.last_edited_at = timezone.now()

    @property
    def is_working_day(self):
        """Indica si esta asignación es un día de trabajo."""
        return self.shift_type.is_working_shift


# =============================================================================
# SWAP REQUEST - Solicitudes de intercambio de turno
# =============================================================================

class SwapRequest(TimeStampedModel, UUIDModel):
    """
    Solicitud de intercambio de turno entre dos traders.
    
    Flujo según SRS:
    1. Trader A crea solicitud → Estado: PENDING
    2. Trader B acepta/rechaza → Estado: ACCEPTED_BY_PEER / REJECTED_BY_PEER
    3. Admin aprueba/rechaza → Estado: APPROVED / REJECTED_BY_ADMIN
    4. Si aprobado: se intercambian los turnos automáticamente
    
    También se envían notificaciones por email/WhatsApp en cada paso.
    """
    
    class Status(models.TextChoices):
        """Estados posibles de la solicitud."""
        PENDING = 'PENDING', _('Pendiente de respuesta del compañero')
        ACCEPTED_BY_PEER = 'ACCEPTED_BY_PEER', _('Aceptado por compañero, pendiente de admin')
        REJECTED_BY_PEER = 'REJECTED_BY_PEER', _('Rechazado por compañero')
        APPROVED = 'APPROVED', _('Aprobado por administrador')
        REJECTED_BY_ADMIN = 'REJECTED_BY_ADMIN', _('Rechazado por administrador')
        CANCELLED = 'CANCELLED', _('Cancelado por solicitante')
    
    # Solicitante y su turno
    requester = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='swap_requests_made',
        verbose_name=_('solicitante'),
        help_text=_('Empleado que inicia la solicitud de intercambio')
    )
    requester_schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='swap_requests_as_offered',
        verbose_name=_('turno ofrecido'),
        help_text=_('Turno que el solicitante ofrece intercambiar')
    )
    # Destinatario y su turno
    target_employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='swap_requests_received',
        verbose_name=_('destinatario'),
        help_text=_('Empleado al que se solicita el intercambio')
    )
    target_schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='swap_requests_as_requested',
        verbose_name=_('turno solicitado'),
        help_text=_('Turno que el solicitante desea obtener')
    )
    # Estado y seguimiento
    status = models.CharField(
        _('estado'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text=_('Estado actual de la solicitud')
    )
    reason = models.TextField(
        _('motivo'),
        blank=True,
        default='',
        help_text=_('Razón de la solicitud de intercambio')
    )
    # Respuestas
    peer_response_at = models.DateTimeField(
        _('fecha de respuesta del compañero'),
        null=True,
        blank=True,
        help_text=_('Cuándo respondió el compañero')
    )
    peer_response_note = models.TextField(
        _('nota del compañero'),
        blank=True,
        default='',
        help_text=_('Comentario del compañero al responder')
    )
    admin_response_at = models.DateTimeField(
        _('fecha de respuesta del admin'),
        null=True,
        blank=True,
        help_text=_('Cuándo respondió el administrador')
    )
    admin_responder = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='swap_requests_processed',
        verbose_name=_('administrador'),
        help_text=_('Administrador que procesó la solicitud')
    )
    admin_response_note = models.TextField(
        _('nota del administrador'),
        blank=True,
        default='',
        help_text=_('Comentario del admin al aprobar/rechazar')
    )

    class Meta:
        verbose_name = _('solicitud de intercambio')
        verbose_name_plural = _('solicitudes de intercambio')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['requester', 'status']),
            models.Index(fields=['target_employee', 'status']),
        ]

    def __str__(self):
        return (
            f"Swap #{self.pk}: {self.requester.employee_id} ↔ "
            f"{self.target_employee.employee_id} ({self.get_status_display()})"
        )

    def clean(self):
        """Validaciones de negocio."""
        super().clean()
        # No puede intercambiar consigo mismo
        if self.requester_id == self.target_employee_id:
            raise ValidationError(
                _('No puedes solicitar intercambio contigo mismo')
            )
        # Los turnos deben ser de fechas diferentes o del mismo día
        # (dependiendo de la política de negocio)

    def can_be_cancelled(self):
        """Indica si la solicitud puede ser cancelada."""
        return self.status in [self.Status.PENDING, self.Status.ACCEPTED_BY_PEER]

    def execute_swap(self):
        """
        Ejecuta el intercambio de turnos tras aprobación.
        
        Este método intercambia los shift_type entre los dos schedules
        y actualiza el historial de ediciones.
        """
        if self.status != self.Status.APPROVED:
            raise ValidationError(_('Solo se pueden ejecutar swaps aprobados'))
        
        # Guardar códigos actuales para historial
        from_code_requester = self.requester_schedule.shift_type.code
        from_code_target = self.target_schedule.shift_type.code
        
        # Intercambiar shift_types
        temp_shift = self.requester_schedule.shift_type
        self.requester_schedule.shift_type = self.target_schedule.shift_type
        self.target_schedule.shift_type = temp_shift
        
        # Actualizar origen y historial
        self.requester_schedule.edit_source = Schedule.EditSource.SWAP
        self.target_schedule.edit_source = Schedule.EditSource.SWAP
        
        self.requester_schedule.add_edit_history(
            self.admin_responder,
            from_code_requester,
            self.requester_schedule.shift_type.code
        )
        self.target_schedule.add_edit_history(
            self.admin_responder,
            from_code_target,
            self.target_schedule.shift_type.code
        )
        
        self.requester_schedule.save()
        self.target_schedule.save()


# =============================================================================
# VACATION - Solicitudes de vacaciones
# =============================================================================

class Vacation(TimeStampedModel, UUIDModel):
    """
    Solicitud de vacaciones de un empleado.
    
    Las vacaciones aprobadas son consideradas por el algoritmo de generación
    para excluir al empleado de las asignaciones durante ese período.
    
    Cuando se aprueba una solicitud, el sistema debe marcar automáticamente
    los schedules del período como VAC (turno de vacaciones).
    """
    
    class Status(models.TextChoices):
        """Estados de la solicitud de vacaciones."""
        PENDING = 'PENDING', _('Pendiente de aprobación')
        APPROVED = 'APPROVED', _('Aprobada')
        REJECTED = 'REJECTED', _('Rechazada')
        CANCELLED = 'CANCELLED', _('Cancelada')
    
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='vacations',
        verbose_name=_('empleado'),
        help_text=_('Empleado que solicita las vacaciones')
    )
    start_date = models.DateField(
        _('fecha de inicio'),
        db_index=True,
        help_text=_('Primer día de vacaciones')
    )
    end_date = models.DateField(
        _('fecha de fin'),
        db_index=True,
        help_text=_('Último día de vacaciones')
    )
    status = models.CharField(
        _('estado'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text=_('Estado de la solicitud')
    )
    reason = models.TextField(
        _('motivo'),
        blank=True,
        default='',
        help_text=_('Razón o notas de la solicitud')
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vacations_approved',
        verbose_name=_('aprobado por'),
        help_text=_('Administrador que aprobó/rechazó la solicitud')
    )
    approved_at = models.DateTimeField(
        _('fecha de aprobación'),
        null=True,
        blank=True,
        help_text=_('Cuándo fue procesada la solicitud')
    )
    rejection_reason = models.TextField(
        _('motivo de rechazo'),
        blank=True,
        default='',
        help_text=_('Explicación si fue rechazada')
    )

    class Meta:
        verbose_name = _('vacaciones')
        verbose_name_plural = _('vacaciones')
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return (
            f"{self.employee.employee_id}: "
            f"{self.start_date} - {self.end_date} ({self.get_status_display()})"
        )

    def clean(self):
        """Validaciones de negocio."""
        super().clean()
        if self.end_date < self.start_date:
            raise ValidationError(
                _('La fecha de fin no puede ser anterior a la fecha de inicio')
            )
        # Validar que no se solapen con otras vacaciones aprobadas
        overlapping = Vacation.objects.filter(
            employee=self.employee,
            status=self.Status.APPROVED,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(pk=self.pk)
        
        if overlapping.exists():
            raise ValidationError(
                _('Ya tienes vacaciones aprobadas que se solapan con este período')
            )

    @property
    def total_days(self):
        """Número total de días de vacaciones."""
        return (self.end_date - self.start_date).days + 1

    def get_dates_range(self):
        """Genera lista de todas las fechas del período."""
        from datetime import timedelta
        current = self.start_date
        dates = []
        while current <= self.end_date:
            dates.append(current)
            current += timedelta(days=1)
        return dates


# =============================================================================
# SYSTEM SETTINGS - Configuración global del sistema (Singleton)
# =============================================================================

class SystemSettingsManager(models.Manager):
    """Manager personalizado para garantizar patrón Singleton."""
    
    def get_settings(self):
        """
        Obtiene la instancia única de configuración.
        La crea si no existe.
        """
        settings, created = self.get_or_create(pk=1)
        return settings


class SystemSettings(TimeStampedModel):
    """
    Configuración global del sistema.
    
    Implementa el patrón Singleton a nivel de aplicación.
    Solo puede existir un registro (pk=1).
    
    Contiene parámetros que afectan el comportamiento del algoritmo
    de generación y las políticas de aprobación.
    """
    # Parámetros del algoritmo
    weekend_scheduling = models.BooleanField(
        _('permitir turnos en fines de semana'),
        default=True,
        help_text=_('Si el algoritmo puede asignar turnos en sábado y domingo')
    )
    max_consecutive_days = models.PositiveSmallIntegerField(
        _('máximo días consecutivos'),
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(14)],
        help_text=_('Máximo de días consecutivos de trabajo permitidos')
    )
    min_rest_hours = models.PositiveSmallIntegerField(
        _('horas mínimas de descanso'),
        default=8,
        validators=[MinValueValidator(6), MaxValueValidator(24)],
        help_text=_('Horas mínimas de descanso entre turnos')
    )
    # Políticas de aprobación
    auto_approval = models.BooleanField(
        _('auto-aprobación de solicitudes'),
        default=False,
        help_text=_('Si los swap requests se aprueban automáticamente tras aceptación del compañero')
    )
    # Notificaciones
    notification_email_enabled = models.BooleanField(
        _('notificaciones por email'),
        default=True,
        help_text=_('Habilitar envío de notificaciones por correo electrónico')
    )
    notification_whatsapp_enabled = models.BooleanField(
        _('notificaciones por WhatsApp'),
        default=False,
        help_text=_('Habilitar envío de notificaciones por WhatsApp')
    )
    # Configuración del algoritmo
    default_algorithm_version = models.CharField(
        _('versión del algoritmo'),
        max_length=20,
        default='v1.0',
        help_text=_('Versión del algoritmo de generación a usar por defecto')
    )
    
    objects = SystemSettingsManager()

    class Meta:
        verbose_name = _('configuración del sistema')
        verbose_name_plural = _('configuración del sistema')

    def __str__(self):
        return "Configuración del Sistema"

    def save(self, *args, **kwargs):
        """Forzar pk=1 para mantener singleton."""
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevenir eliminación del singleton."""
        pass  # No hacer nada

    @classmethod
    def load(cls):
        """Método de conveniencia para obtener la configuración."""
        return cls.objects.get_settings()


# =============================================================================
# SCHEDULE GENERATION LOG - Auditoría de generaciones automáticas
# =============================================================================

class ScheduleGenerationLog(TimeStampedModel):
    """
    Registro de auditoría para las ejecuciones del algoritmo de generación.
    
    Cada vez que se ejecuta la generación automática de horarios,
    se crea un registro con los parámetros, resultados y cualquier
    advertencia o error.
    
    Útil para debugging y para entender las decisiones del algoritmo.
    """
    
    class Status(models.TextChoices):
        """Estados de la generación."""
        SUCCESS = 'SUCCESS', _('Completado exitosamente')
        PARTIAL = 'PARTIAL', _('Completado con advertencias')
        FAILED = 'FAILED', _('Fallido')
        CANCELLED = 'CANCELLED', _('Cancelado por usuario')
    
    month = models.PositiveSmallIntegerField(
        _('mes'),
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text=_('Mes para el que se generó el horario (1-12)')
    )
    year = models.PositiveSmallIntegerField(
        _('año'),
        validators=[MinValueValidator(2020), MaxValueValidator(2100)],
        help_text=_('Año para el que se generó el horario')
    )
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='schedule_generations',
        verbose_name=_('generado por'),
        help_text=_('Usuario que ejecutó la generación')
    )
    status = models.CharField(
        _('estado'),
        max_length=20,
        choices=Status.choices,
        default=Status.SUCCESS,
        db_index=True,
        help_text=_('Resultado de la generación')
    )
    # Métricas
    total_assignments = models.PositiveIntegerField(
        _('total de asignaciones'),
        default=0,
        help_text=_('Número de asignaciones creadas')
    )
    events_considered = models.PositiveIntegerField(
        _('eventos considerados'),
        default=0,
        help_text=_('Número de eventos deportivos considerados')
    )
    traders_scheduled = models.PositiveIntegerField(
        _('traders programados'),
        default=0,
        help_text=_('Número de traders incluidos en el horario')
    )
    # Logs detallados
    warnings = models.JSONField(
        _('advertencias'),
        default=list,
        blank=True,
        help_text=_('Lista de advertencias durante la generación')
    )
    errors = models.JSONField(
        _('errores'),
        default=list,
        blank=True,
        help_text=_('Lista de errores durante la generación')
    )
    algorithm_decisions = models.JSONField(
        _('decisiones del algoritmo'),
        default=list,
        blank=True,
        help_text=_('Log de decisiones tomadas por el algoritmo')
    )
    # Performance
    execution_time_seconds = models.FloatField(
        _('tiempo de ejecución'),
        default=0.0,
        help_text=_('Tiempo total de ejecución en segundos')
    )
    algorithm_version = models.CharField(
        _('versión del algoritmo'),
        max_length=20,
        default='v1.0',
        help_text=_('Versión del algoritmo utilizada')
    )
    # Parámetros usados
    parameters_snapshot = models.JSONField(
        _('parámetros'),
        default=dict,
        blank=True,
        help_text=_('Snapshot de los parámetros usados (min_traders, etc.)')
    )

    class Meta:
        verbose_name = _('log de generación')
        verbose_name_plural = _('logs de generación')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return (
            f"Generación {self.month}/{self.year} - "
            f"{self.get_status_display()} ({self.total_assignments} asignaciones)"
        )

    @property
    def period_display(self):
        """Retorna el período en formato legible."""
        import calendar
        month_name = calendar.month_name[self.month]
        return f"{month_name} {self.year}"


# =============================================================================
# SIGNALS - Señales para lógica automática
# =============================================================================
# Nota: Los signals se definen aquí pero se conectan en apps.py
# para evitar problemas de importación circular.

# Ejemplo de uso (implementar en signals.py):
# 
# @receiver(post_save, sender=Vacation)
# def create_vacation_schedules(sender, instance, created, **kwargs):
#     """Crea automáticamente schedules con VAC cuando se aprueba una vacación."""
#     if instance.status == Vacation.Status.APPROVED:
#         vac_shift = ShiftType.objects.get(code='VAC')
#         for date in instance.get_dates_range():
#             Schedule.objects.update_or_create(
#                 employee=instance.employee,
#                 date=date,
#                 defaults={
#                     'shift_type': vac_shift,
#                     'edit_source': Schedule.EditSource.MANUAL,
#                 }
#             )