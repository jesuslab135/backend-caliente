"""
SquadUp - Django Models (Refactorizado)
=======================================
Basado en el análisis del SRS y corrigiendo los problemas detectados en la versión anterior.

CAMBIOS PRINCIPALES:
1. Modelo User compatible con Firebase Auth
2. Corrección de relaciones incorrectas (ForeignKey vs OneToOneField)
3. Adición de modelos faltantes según el SRS (Friendship, BlitzInteraction, Notification)
4. Corrección del error crítico en Message.chat_id
5. Adición de campos requeridos para la lógica de Blitz
"""

from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

class UserBillingMixin:
    """
    Mixin que agrega funcionalidad de billing al modelo User.
    
    INTEGRACIÓN CON USER:
    El modelo User existente (con Firebase Auth) se relaciona con billing así:
    - User.subscriptions → Todas las suscripciones del usuario
    - User.payment_methods → Métodos de pago guardados
    - User.invoices → Facturas generadas
    
    Para usarlo, tu clase User debe heredar de este mixin:
    
    class User(UserBillingMixin, models.Model):
        first_name = ...
        firebase_uid = ...
    """
    
    @property
    def active_subscription(self):
        """
        Retorna la suscripción activa actual del usuario.
        
        DISEÑO FREEMIUM:
        Todo usuario SIEMPRE tiene una suscripción (aunque sea Free).
        Este método retorna la más reciente activa.
        """
        return self.subscriptions.filter(
            status__in=['trialing', 'active', 'past_due']
        ).order_by('-created_at').first()
    
    @property
    def current_plan(self):
        """Retorna el plan actual del usuario."""
        subscription = self.active_subscription
        if subscription:
            return subscription.plan
        return None
    
    @property
    def is_premium(self):
        """¿El usuario tiene acceso premium?"""
        plan = self.current_plan
        if not plan:
            return False
        return plan.plan_type in ['premium', 'enterprise']
    
    @property
    def is_trialing(self):
        """¿El usuario está en periodo de prueba?"""
        subscription = self.active_subscription
        return subscription and subscription.status == 'trialing'
    
    @property
    def default_payment_method(self):
        """Retorna el método de pago predeterminado."""
        return self.payment_methods.filter(
            is_default=True, 
            is_valid=True
        ).first()
    
    def has_feature(self, feature_key: str) -> bool:
        """
        Verifica si el usuario tiene acceso a una feature.
        
        USO:
            if user.has_feature('unlimited_blitz'):
                allow_action()
        """
        plan = self.current_plan
        if not plan:
            return False
        
        try:
            feature = plan.features.get(feature_key=feature_key)
            return feature.as_bool
        except PlanFeature.DoesNotExist:
            return False
    
    def get_feature_limit(self, feature_key: str) -> int:
        """
        Obtiene el límite numérico de una feature.
        
        Retorna:
        - -1 si es ilimitado
        - 0 si la feature no existe
        - N si tiene un límite específico
        
        USO:
            max_groups = user.get_feature_limit('max_groups')
            if max_groups == -1 or current_groups < max_groups:
                allow_create_group()
        """
        plan = self.current_plan
        if not plan:
            return 0
        
        try:
            feature = plan.features.get(feature_key=feature_key)
            return feature.as_int
        except PlanFeature.DoesNotExist:
            return 0
    
    def get_usage(self, feature_key: str) -> int:
        """
        Obtiene el uso actual de una feature en el periodo de facturación.
        """
        subscription = self.active_subscription
        if not subscription:
            return 0
        
        # Obtener el uso del periodo actual
        usage = UsageRecord.objects.filter(
            subscription=subscription,
            feature_key=feature_key,
            period_start__lte=timezone.now(),
            period_end__gte=timezone.now()
        ).aggregate(total=models.Sum('quantity'))
        
        return usage['total'] or 0
    
    def can_use_feature(self, feature_key: str, quantity: int = 1) -> tuple:
        """
        Verifica si el usuario puede usar una feature.
        
        Retorna: (bool, str) - (puede_usar, mensaje)
        
        USO:
            can_create, message = user.can_use_feature('max_groups')
            if not can_create:
                return Response({'error': message}, status=403)
        """
        limit = self.get_feature_limit(feature_key)
        
        if limit == -1:  # Ilimitado
            return True, "OK"
        
        if limit == 0:  # Feature no disponible
            return False, f"Esta función no está disponible en tu plan actual."
        
        current_usage = self.get_usage(feature_key)
        
        if current_usage + quantity > limit:
            remaining = limit - current_usage
            return False, f"Has alcanzado el límite de tu plan. Disponible: {remaining}."
        
        return True, "OK"

# =============================================================================
# USER MODEL
# =============================================================================
class User(UserBillingMixin, models.Model):
    """
    Modelo de Usuario compatible con Firebase Authentication.
    
    CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
    - Se mantiene como modelo independiente (no AbstractUser) porque Firebase
      maneja la autenticación. Django solo almacena datos de perfil.
    - AÑADIDO: 'profile_photo' - Requerido por RF-003 (identificación con foto)
    - AÑADIDO: 'is_verified' - Para el proceso de verificación de identidad
    - CORREGIDO: 'firebase_uid' ahora tiene unique=True para evitar duplicados
    """
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=254, unique=True)  # CORREGIDO: añadido unique=True
    phone = models.CharField(max_length=16, blank=True, default="")
    
    # Firebase Integration
    # CORREGIDO: Antes no tenía unique=True, lo cual podría causar usuarios duplicados
    firebase_uid = models.CharField(max_length=128, unique=True, db_index=True)
    
    # AÑADIDO: Campos requeridos por RF-003 (User Identification)
    profile_photo = models.URLField(max_length=500, blank=True, default="")
    is_verified = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    
    # CORREGIDO: El campo 'json' era muy genérico. Renombrado para claridad.
    # Almacena preferencias del usuario para el algoritmo de recomendación (RF-013)
    preferences = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['firebase_uid']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


# =============================================================================
# FRIENDSHIP MODEL (NUEVO)
# =============================================================================
class Friendship(models.Model):
    """
    NUEVO MODELO - Requerido por RF-004 (Friend Management)
    
    La versión anterior NO tenía este modelo, lo cual hacía imposible
    implementar la gestión de amigos requerida por el SRS.
    
    Diseño bidireccional: cuando user_1 y user_2 son amigos, solo se crea
    UN registro (user_1.id < user_2.id para consistencia).
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        ACCEPTED = 'accepted', 'Aceptado'
        REJECTED = 'rejected', 'Rechazado'
        BLOCKED = 'blocked', 'Bloqueado'
    
    # Siempre user_from.id < user_to.id para evitar duplicados
    user_from = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='friendships_initiated'
    )
    user_to = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='friendships_received'
    )
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'friendships'
        # Evita solicitudes de amistad duplicadas
        unique_together = ('user_from', 'user_to')
        indexes = [
            models.Index(fields=['user_from', 'status']),
            models.Index(fields=['user_to', 'status']),
        ]

    def __str__(self):
        return f"{self.user_from} -> {self.user_to} ({self.status})"


# =============================================================================
# GROUP MODEL
# =============================================================================
class Group(models.Model):
    """
    Modelo de Grupo para sesiones Blitz.
    
    CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
    - AÑADIDO: 'name' - Los grupos necesitan un nombre identificable
    - AÑADIDO: 'creator' - Referencia al usuario que creó el grupo
    - AÑADIDO: 'is_active' - Para soft delete
    - CORREGIDO: 'json' renombrado a 'metadata' para claridad
    - AÑADIDO: Validación de mínimo 2 miembros (RF-005) se hace a nivel de aplicación
    """
    name = models.CharField(max_length=100, default="Mi Grupo")
    description = models.TextField(blank=True, default="")
    
    # AÑADIDO: Creador del grupo (importante para permisos)
    creator = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_groups'
    )
    
    # Miembros del grupo
    members = models.ManyToManyField(
        User, 
        through='GroupMembership',  # AÑADIDO: Tabla intermedia para más control
        related_name='groups'
    )
    
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)  # RENOMBRADO de 'json'
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'groups'

    def __str__(self):
        return self.name
    
    @property
    def member_count(self):
        return self.members.count()


# =============================================================================
# GROUP MEMBERSHIP (NUEVO)
# =============================================================================
class GroupMembership(models.Model):
    """
    NUEVO MODELO - Tabla intermedia para la relación User-Group
    
    La versión anterior usaba ManyToManyField directo, lo cual no permitía
    almacenar información adicional como:
    - Fecha de unión al grupo
    - Rol dentro del grupo (útil para el Blitz Leader de RF-006)
    """
    class Role(models.TextChoices):
        MEMBER = 'member', 'Miembro'
        ADMIN = 'admin', 'Administrador'
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_memberships'
        unique_together = ('user', 'group')

    def __str__(self):
        return f"{self.user} in {self.group} ({self.role})"


# =============================================================================
# PROFILE MODEL
# =============================================================================
class Profile(models.Model):
    """
    Perfil extendido del usuario.
    
    CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
    - CORREGIDO: 'user_id' cambiado a 'user' (convención Django)
    - CORREGIDO: ForeignKey cambiado a OneToOneField (un usuario = un perfil)
    - AÑADIDO: Campos para preferencias sociales (útil para RF-013 algoritmo)
    """
    # CORREGIDO: Antes era ForeignKey, lo cual permitía múltiples perfiles por usuario
    # OneToOneField garantiza la relación 1:1
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    
    bio = models.TextField(blank=True, default="")
    
    # AÑADIDO: Preferencias para el algoritmo de recomendación (RF-013)
    interests = models.JSONField(default=list, blank=True)  # ["música", "deportes", etc.]
    age = models.PositiveIntegerField(null=True, blank=True)
    
    # RENOMBRADO: 'json' a 'extra_data' para claridad
    extra_data = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'profiles'

    def __str__(self):
        return f"Profile of {self.user}"


# =============================================================================
# BLITZ MODEL
# =============================================================================

# Duración por defecto de una sesión Blitz (RF-012)
BLITZ_DEFAULT_DURATION_MINUTES = 60


class Blitz(models.Model):
    """
    Sesión Blitz - Estado temporal de disponibilidad de un grupo.
    
    CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
    - CORREGIDO: 'group_id' renombrado a 'group' (convención Django)
    - AÑADIDO: 'status' - El modelo anterior no tenía estado (activo/expirado)
    - AÑADIDO: 'leader' - Requerido por RF-006 (Blitz Leader)
    - AÑADIDO: 'expires_at' - Requerido por RF-012 (expiración automática)
    - AÑADIDO: 'activity_type' - Contexto de la actividad (qué quieren hacer)
    - MEJORADO: 'location' ahora tiene estructura definida
    """
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Activo'
        EXPIRED = 'expired', 'Expirado'
        CANCELLED = 'cancelled', 'Cancelado'
        MATCHED = 'matched', 'Emparejado'
    
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE, 
        related_name='blitz_sessions'
    )
    
    # AÑADIDO: Blitz Leader (RF-006) - Usuario que toma decisiones durante el Blitz
    leader = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='led_blitz_sessions'
    )
    
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.ACTIVE
    )
    
    # AÑADIDO: Campos de tiempo para RF-012 (Blitz Session Expiration)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    
    # Ubicación para RF-007 (Blitz Group Discovery) y RF-014 (Heat Map)
    # Estructura: {"lat": float, "lng": float, "address": str, "radius_km": float}
    location = models.JSONField(default=dict)
    
    # AÑADIDO: Tipo de actividad que busca el grupo
    activity_type = models.CharField(max_length=100, blank=True, default="")
    
    # Datos adicionales (preferencias de match, etc.)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'blitz_sessions'
        verbose_name_plural = 'Blitz Sessions'
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Blitz: {self.group.name} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Auto-establecer expires_at si no está definido
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=BLITZ_DEFAULT_DURATION_MINUTES)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at or self.status != self.Status.ACTIVE


# =============================================================================
# BLITZ INTERACTION (NUEVO)
# =============================================================================
class BlitzInteraction(models.Model):
    """
    NUEVO MODELO - Requerido por RF-008 (Fast Group Interaction)
    
    La versión anterior NO tenía forma de registrar los likes/skips.
    Este modelo almacena cada interacción entre grupos en Blitz.
    """
    class InteractionType(models.TextChoices):
        LIKE = 'like', 'Like'
        SKIP = 'skip', 'Skip'
    
    # El Blitz que realiza la interacción
    from_blitz = models.ForeignKey(
        Blitz, 
        on_delete=models.CASCADE, 
        related_name='interactions_made'
    )
    
    # El Blitz que recibe la interacción
    to_blitz = models.ForeignKey(
        Blitz, 
        on_delete=models.CASCADE, 
        related_name='interactions_received'
    )
    
    interaction_type = models.CharField(
        max_length=10, 
        choices=InteractionType.choices
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blitz_interactions'
        # Un grupo solo puede interactuar una vez con otro grupo por sesión
        unique_together = ('from_blitz', 'to_blitz')
        indexes = [
            models.Index(fields=['from_blitz', 'interaction_type']),
            models.Index(fields=['to_blitz', 'interaction_type']),
        ]

    def __str__(self):
        return f"{self.from_blitz.group.name} -> {self.to_blitz.group.name}: {self.interaction_type}"


# =============================================================================
# MATCH MODEL
# =============================================================================
class Match(models.Model):
    """
    Blitz Match - Cuando dos grupos hacen like mutuo (RF-010).
    
    CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
    - CORREGIDO: 'blitz_id' y 'blitz_id_2' renombrados a 'blitz_1' y 'blitz_2'
    - AÑADIDO: 'status' - Para tracking del estado del match
    - AÑADIDO: 'chat' - Referencia al chat creado (RF-011)
    - RENOMBRADO: 'json' a 'metadata'
    """
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Activo'
        CHATTING = 'chatting', 'En Chat'
        MET = 'met', 'Se Encontraron'
        EXPIRED = 'expired', 'Expirado'
        CANCELLED = 'cancelled', 'Cancelado'
    
    blitz_1 = models.ForeignKey(
        Blitz, 
        on_delete=models.CASCADE, 
        related_name='matches_as_first'
    )
    blitz_2 = models.ForeignKey(
        Blitz, 
        on_delete=models.CASCADE, 
        related_name='matches_as_second'
    )
    
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.ACTIVE
    )
    
    # AÑADIDO: Referencia al chat temporal (RF-011)
    # Se crea automáticamente al formar el match
    chat = models.OneToOneField(
        'Chat', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='match'
    )
    
    # Ubicación acordada para el encuentro (opcional)
    meeting_location = models.JSONField(null=True, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'matches'
        verbose_name_plural = 'Matches'
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Match: {self.blitz_1.group.name} <-> {self.blitz_2.group.name}"


# =============================================================================
# CHAT MODEL
# =============================================================================
class Chat(models.Model):
    """
    Chat temporal para coordinación (RF-011).
    
    CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
    - AÑADIDO: 'is_active' - Los chats son temporales y pueden desactivarse
    - AÑADIDO: 'expires_at' - Para limpieza automática
    - AÑADIDO: Relación con participantes
    - RENOMBRADO: 'json' a 'metadata'
    """
    # Los participantes son todos los usuarios de ambos grupos del Match
    participants = models.ManyToManyField(
        User, 
        related_name='chats'
    )
    
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chats'

    def __str__(self):
        return f"Chat {self.id} ({'active' if self.is_active else 'inactive'})"


# =============================================================================
# MESSAGE MODEL
# =============================================================================
class Message(models.Model):
    """
    Mensaje dentro de un chat.
    
    CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
    - ⚠️ ERROR CRÍTICO CORREGIDO: 'chat_id' apuntaba a User en lugar de Chat
      Esto hacía IMPOSIBLE asociar mensajes con chats correctamente.
    - CORREGIDO: 'user_id' renombrado a 'sender' (convención y claridad)
    - AÑADIDO: 'message_type' - Para soportar diferentes tipos de contenido
    - AÑADIDO: 'is_read' - Para tracking de mensajes leídos
    """
    class MessageType(models.TextChoices):
        TEXT = 'text', 'Texto'
        IMAGE = 'image', 'Imagen'
        LOCATION = 'location', 'Ubicación'
        SYSTEM = 'system', 'Sistema'
    
    # CORREGIDO: Antes apuntaba a User (ERROR GRAVE)
    # Ahora apunta correctamente a Chat
    chat = models.ForeignKey(
        Chat, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    
    # RENOMBRADO: 'user_id' -> 'sender' para mayor claridad
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_messages'
    )
    
    text = models.TextField(default="")
    message_type = models.CharField(
        max_length=20, 
        choices=MessageType.choices, 
        default=MessageType.TEXT
    )
    
    # AÑADIDO: Para tracking de mensajes leídos
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Para contenido adicional (URL de imagen, coordenadas, etc.)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['chat', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
        ]

    def __str__(self):
        return f"{self.sender}: {self.text[:50]}..."


# =============================================================================
# NOTIFICATION MODEL (NUEVO)
# =============================================================================
class Notification(models.Model):
    """
    NUEVO MODELO - Requerido por RF-009 (Instant Notifications)
    
    La versión anterior NO tenía modelo de notificaciones, lo cual hacía
    imposible implementar el requisito RF-009 del SRS.
    """
    class NotificationType(models.TextChoices):
        BLITZ_MATCH = 'blitz_match', 'Nuevo Match'
        BLITZ_LIKE = 'blitz_like', 'Grupo te dio Like'
        NEW_MESSAGE = 'new_message', 'Nuevo Mensaje'
        FRIEND_REQUEST = 'friend_request', 'Solicitud de Amistad'
        GROUP_INVITE = 'group_invite', 'Invitación a Grupo'
        BLITZ_EXPIRING = 'blitz_expiring', 'Blitz por Expirar'
        SYSTEM = 'system', 'Sistema'
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    
    notification_type = models.CharField(
        max_length=30, 
        choices=NotificationType.choices
    )
    
    title = models.CharField(max_length=200)
    body = models.TextField()
    
    # Datos adicionales para la acción (ej: ID del match, chat, etc.)
    data = models.JSONField(default=dict, blank=True)
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Para integración con Firebase Cloud Messaging
    fcm_sent = models.BooleanField(default=False)
    fcm_sent_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
            models.Index(fields=['user', 'notification_type']),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.title}"


# =============================================================================
# LOCATION LOG (NUEVO) - Para Heat Map (RF-014)
# =============================================================================
class LocationLog(models.Model):
    """
    NUEVO MODELO - Requerido por RF-014 (Meeting Heat Map)
    
    Registra ubicaciones de actividad para generar el mapa de calor
    de zonas con alta densidad de grupos.
    """
    # Puede ser un log de un Blitz activo o de un Match completado
    blitz = models.ForeignKey(
        Blitz, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='location_logs'
    )
    match = models.ForeignKey(
        Match, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='location_logs'
    )
    
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Tipo de evento para el heat map
    event_type = models.CharField(max_length=50)  # 'blitz_active', 'match_created', 'meeting'
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'location_logs'
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]

    def __str__(self):
        return f"Location ({self.latitude}, {self.longitude}) - {self.event_type}"


# =============================================================================
# PLAN MODEL - La Oferta Comercial
# =============================================================================
class Plan(models.Model):
    """
    Define los planes disponibles en el sistema (Free, Premium, etc.)
    
    IMPORTANTE: Un Plan es la OFERTA, no la instancia del usuario.
    Múltiples usuarios pueden estar suscritos al mismo Plan.
    
    DISEÑO AGNÓSTICO:
    - 'external_id' almacena el ID del plan en la pasarela externa
    - Permite mapear a Stripe Price ID, PayPal Plan ID, etc.
    """
    
    class BillingInterval(models.TextChoices):
        """
        Intervalos de facturación soportados.
        'LIFETIME' es para compras únicas (no renovables).
        """
        MONTHLY = 'monthly', 'Mensual'
        QUARTERLY = 'quarterly', 'Trimestral'
        YEARLY = 'yearly', 'Anual'
        LIFETIME = 'lifetime', 'Vitalicio'
    
    class PlanType(models.TextChoices):
        """
        Tipos de plan para lógica de negocio.
        FREE siempre debe existir como fallback.
        """
        FREE = 'free', 'Gratuito'
        PREMIUM = 'premium', 'Premium'
        ENTERPRISE = 'enterprise', 'Empresarial'
    
    # Identificadores
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # AGNÓSTICO: ID en la pasarela de pago externa (Stripe price_id, etc.)
    # Puede ser NULL para el plan Free que no requiere pasarela
    external_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        db_index=True,
        help_text="ID del plan en la pasarela de pago (ej: price_xxxxx en Stripe)"
    )
    
    # Información del plan
    name = models.CharField(max_length=100)  # "Premium Mensual", "Premium Anual"
    slug = models.SlugField(unique=True)  # "premium-monthly", "premium-yearly"
    description = models.TextField(blank=True, default="")
    plan_type = models.CharField(
        max_length=20, 
        choices=PlanType.choices,
        default=PlanType.FREE
    )
    
    # Precio y facturación
    # IMPORTANTE: Usar Decimal para dinero, NUNCA float (errores de precisión)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.CharField(max_length=3, default='MXN')  # ISO 4217
    billing_interval = models.CharField(
        max_length=20,
        choices=BillingInterval.choices,
        default=BillingInterval.MONTHLY
    )
    
    # Trial (periodo de prueba)
    # FREEMIUM: Permite ofrecer X días gratis de Premium antes de cobrar
    trial_days = models.PositiveIntegerField(
        default=0,
        help_text="Días de prueba gratuita (0 = sin trial)"
    )
    
    # Control de disponibilidad
    is_active = models.BooleanField(
        default=True,
        help_text="Si está disponible para nuevas suscripciones"
    )
    is_public = models.BooleanField(
        default=True,
        help_text="Si aparece en la UI pública (False para planes legacy)"
    )
    
    # Orden de display en UI
    display_order = models.PositiveIntegerField(default=0)
    
    # Metadata flexible para características adicionales
    metadata = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Datos adicionales del plan (límites, características, etc.)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_plans'
        ordering = ['display_order', 'price']

    def __str__(self):
        return f"{self.name} ({self.price} {self.currency}/{self.billing_interval})"
    
    @property
    def is_free(self):
        return self.plan_type == self.PlanType.FREE or self.price == Decimal('0.00')
    
    @property
    def interval_days(self):
        """Retorna la cantidad de días del intervalo de facturación."""
        intervals = {
            'monthly': 30,
            'quarterly': 90,
            'yearly': 365,
            'lifetime': 36500,  # ~100 años
        }
        return intervals.get(self.billing_interval, 30)


# =============================================================================
# PLAN FEATURE - Feature Flags por Plan
# =============================================================================
class PlanFeature(models.Model):
    """
    Define las características/límites de cada plan.
    
    DISEÑO FLEXIBLE:
    Permite definir tanto booleanos (tiene_feature) como límites numéricos
    (max_grupos: 3) usando el campo 'value'.
    
    EJEMPLO DE USO EN CÓDIGO:
    ```python
    def can_create_group(user):
        feature = user.subscription.plan.features.get(feature_key='max_groups')
        current_count = user.created_groups.count()
        return current_count < int(feature.value)
    ```
    """
    
    plan = models.ForeignKey(
        Plan, 
        on_delete=models.CASCADE, 
        related_name='features'
    )
    
    # Clave programática (usar en código)
    feature_key = models.CharField(
        max_length=100,
        help_text="Clave única para usar en código (ej: 'max_groups', 'unlimited_blitz')"
    )
    
    # Nombre legible (usar en UI)
    feature_name = models.CharField(
        max_length=200,
        help_text="Nombre para mostrar al usuario (ej: 'Grupos máximos')"
    )
    
    # Valor de la característica
    # Puede ser: "true"/"false" para booleanos, o número para límites
    value = models.CharField(
        max_length=100,
        help_text="Valor: 'true'/'false' para flags, número para límites, 'unlimited' para sin límite"
    )
    
    # Descripción para marketing
    description = models.TextField(
        blank=True, 
        default="",
        help_text="Descripción para mostrar en página de precios"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_plan_features'
        unique_together = ('plan', 'feature_key')

    def __str__(self):
        return f"{self.plan.name}: {self.feature_key} = {self.value}"
    
    @property
    def as_bool(self):
        """Convierte el valor a booleano."""
        return self.value.lower() in ('true', '1', 'yes', 'unlimited')
    
    @property
    def as_int(self):
        """Convierte el valor a entero. Retorna -1 si es 'unlimited'."""
        if self.value.lower() == 'unlimited':
            return -1  # -1 indica sin límite
        try:
            return int(self.value)
        except ValueError:
            return 0


# =============================================================================
# PAYMENT METHOD - Métodos de Pago del Usuario
# =============================================================================
class PaymentMethod(models.Model):
    """
    Almacena los métodos de pago guardados del usuario.
    
    DISEÑO AGNÓSTICO:
    - 'provider' identifica la pasarela (stripe, paypal, mercadopago)
    - 'external_id' es el ID del método en esa pasarela
    - NUNCA almacenamos datos sensibles (número de tarjeta, CVV)
    - Solo guardamos los últimos 4 dígitos para display
    
    SEGURIDAD:
    Los datos reales de pago viven en la pasarela externa.
    Este modelo solo guarda referencias y metadata para UX.
    """
    
    class Provider(models.TextChoices):
        STRIPE = 'stripe', 'Stripe'
        PAYPAL = 'paypal', 'PayPal'
        MERCADOPAGO = 'mercadopago', 'MercadoPago'
        CONEKTA = 'conekta', 'Conekta'
        MANUAL = 'manual', 'Manual/Transferencia'
    
    class MethodType(models.TextChoices):
        CARD = 'card', 'Tarjeta de Crédito/Débito'
        PAYPAL = 'paypal', 'PayPal'
        BANK_TRANSFER = 'bank_transfer', 'Transferencia Bancaria'
        OXXO = 'oxxo', 'OXXO'
        SPEI = 'spei', 'SPEI'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relación con User (del archivo models.py principal)
    user = models.ForeignKey(
        'User',  # String reference para evitar imports circulares
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    
    # AGNÓSTICO: Identificación en pasarela externa
    provider = models.CharField(max_length=30, choices=Provider.choices)
    external_id = models.CharField(
        max_length=255,
        help_text="ID del método en la pasarela (ej: pm_xxxx en Stripe)"
    )
    
    method_type = models.CharField(max_length=30, choices=MethodType.choices)
    
    # Datos de display (NO SENSIBLES)
    # Para tarjetas: últimos 4 dígitos
    last_four = models.CharField(
        max_length=4, 
        blank=True, 
        default="",
        help_text="Últimos 4 dígitos (solo para display)"
    )
    # Para tarjetas: marca (Visa, Mastercard, etc.)
    card_brand = models.CharField(max_length=50, blank=True, default="")
    # Mes/Año de expiración
    exp_month = models.PositiveSmallIntegerField(null=True, blank=True)
    exp_year = models.PositiveSmallIntegerField(null=True, blank=True)
    
    # Para PayPal: email asociado
    billing_email = models.EmailField(blank=True, default="")
    
    # Estado
    is_default = models.BooleanField(
        default=False,
        help_text="Si es el método de pago predeterminado"
    )
    is_valid = models.BooleanField(
        default=True,
        help_text="Si el método sigue siendo válido (puede expirar o ser rechazado)"
    )
    
    # Dirección de facturación (opcional pero recomendado)
    billing_address = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Dirección de facturación: {street, city, state, postal_code, country}"
    )
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_payment_methods'
        indexes = [
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['provider', 'external_id']),
        ]

    def __str__(self):
        if self.method_type == self.MethodType.CARD:
            return f"{self.card_brand} ****{self.last_four}"
        return f"{self.method_type} ({self.provider})"
    
    def save(self, *args, **kwargs):
        # Si este método se marca como default, desmarcar los demás
        if self.is_default:
            PaymentMethod.objects.filter(
                user=self.user, 
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


# =============================================================================
# SUBSCRIPTION - La Instancia del Usuario en un Plan
# =============================================================================
class Subscription(models.Model):
    """
    Representa la suscripción activa de un usuario a un plan.
    
    CICLO DE VIDA TÍPICO:
    1. TRIALING → Usuario en periodo de prueba gratuito
    2. ACTIVE → Suscripción activa y al día
    3. PAST_DUE → Pago fallido, en periodo de gracia
    4. UNPAID → Periodo de gracia terminado, servicio limitado
    5. CANCELED → Usuario canceló (puede tener acceso hasta period_end)
    6. EXPIRED → Suscripción terminada completamente
    
    DISEÑO AGNÓSTICO:
    - 'external_id' mapea a la suscripción en la pasarela
    - Permite sincronizar estados con Stripe Subscription, etc.
    
    FREEMIUM:
    - Todo usuario SIEMPRE tiene una Subscription (aunque sea al plan Free)
    - Esto simplifica el código: user.subscription.plan siempre existe
    """
    
    class Status(models.TextChoices):
        # Estados activos (usuario tiene acceso)
        TRIALING = 'trialing', 'En Prueba'
        ACTIVE = 'active', 'Activa'
        
        # Estados problemáticos (acceso limitado o en riesgo)
        PAST_DUE = 'past_due', 'Pago Vencido'
        UNPAID = 'unpaid', 'Impaga'
        
        # Estados terminales
        CANCELED = 'canceled', 'Cancelada'
        EXPIRED = 'expired', 'Expirada'
        
        # Estado especial
        PAUSED = 'paused', 'Pausada'
    
    class CancelReason(models.TextChoices):
        """Razones de cancelación para analytics."""
        USER_REQUEST = 'user_request', 'Solicitud del Usuario'
        PAYMENT_FAILED = 'payment_failed', 'Pago Fallido'
        FRAUD = 'fraud', 'Fraude Detectado'
        ADMIN = 'admin', 'Cancelado por Admin'
        UPGRADED = 'upgraded', 'Upgrade a Otro Plan'
        DOWNGRADED = 'downgraded', 'Downgrade a Otro Plan'
        OTHER = 'other', 'Otro'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relaciones principales
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,  # PROTECT: no permitir borrar planes con suscripciones
        related_name='subscriptions'
    )
    
    # AGNÓSTICO: ID en pasarela externa
    external_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        db_index=True,
        help_text="ID de suscripción en pasarela (ej: sub_xxxx en Stripe)"
    )
    
    # Estado actual
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    
    # =========================================================================
    # FECHAS CRÍTICAS DEL CICLO DE SUSCRIPCIÓN
    # =========================================================================
    
    # Inicio de la suscripción
    started_at = models.DateTimeField(default=timezone.now)
    
    # Periodo actual de facturación
    # IMPORTANTE: Estas fechas definen cuándo cobrar
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(
        help_text="Fecha en que termina el periodo actual y se debe renovar/cobrar"
    )
    
    # Trial (periodo de prueba)
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Si está en trial, fecha en que termina y se cobra"
    )
    
    # Cancelación
    canceled_at = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="Si True, se cancela al final del periodo actual (no inmediatamente)"
    )
    cancel_reason = models.CharField(
        max_length=30,
        choices=CancelReason.choices,
        null=True,
        blank=True
    )
    
    # Periodo de gracia para pagos fallidos
    # FREEMIUM CRÍTICO: Permite X días extra antes de downgrade
    grace_period_end = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Si está en past_due, fecha límite para pagar antes de suspensión"
    )
    
    # Método de pago asociado (el que se usará para renovaciones)
    default_payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions'
    )
    
    # Contadores y tracking
    billing_cycle_count = models.PositiveIntegerField(
        default=0,
        help_text="Número de ciclos de facturación completados"
    )
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_subscriptions'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'current_period_end']),
            models.Index(fields=['external_id']),
        ]

    def __str__(self):
        return f"{self.user} - {self.plan.name} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Auto-calcular current_period_end si no está definido
        if not self.current_period_end:
            self.current_period_end = self.current_period_start + timedelta(
                days=self.plan.interval_days
            )
        super().save(*args, **kwargs)
    
    # =========================================================================
    # PROPIEDADES ÚTILES
    # =========================================================================
    
    @property
    def is_active(self):
        """¿El usuario tiene acceso al servicio premium?"""
        return self.status in [
            self.Status.TRIALING,
            self.Status.ACTIVE,
            self.Status.PAST_DUE,  # Aún tiene acceso durante grace period
        ]
    
    @property
    def is_trialing(self):
        return self.status == self.Status.TRIALING
    
    @property
    def is_on_grace_period(self):
        """¿Está en periodo de gracia por pago fallido?"""
        if self.status != self.Status.PAST_DUE:
            return False
        if not self.grace_period_end:
            return False
        return timezone.now() < self.grace_period_end
    
    @property
    def days_until_renewal(self):
        """Días hasta la próxima renovación."""
        if not self.current_period_end:
            return 0
        delta = self.current_period_end - timezone.now()
        return max(0, delta.days)
    
    @property
    def will_cancel(self):
        """¿Se cancelará al final del periodo?"""
        return self.cancel_at_period_end and self.status == self.Status.ACTIVE


# =============================================================================
# INVOICE - Facturas
# =============================================================================
class Invoice(models.Model):
    """
    Documento de facturación generado para cada cobro.
    
    FLUJO:
    1. Se crea Invoice con status='draft' al inicio del periodo
    2. Se intenta cobrar → status='open'
    3. Si pago exitoso → status='paid'
    4. Si falla → status='open' (se reintenta)
    5. Si no se puede cobrar → status='uncollectible' o 'void'
    
    DISEÑO AGNÓSTICO:
    - 'external_id' mapea a Invoice en pasarela
    - Permite sincronizar con Stripe Invoice, etc.
    """
    
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        OPEN = 'open', 'Abierta'
        PAID = 'paid', 'Pagada'
        VOID = 'void', 'Anulada'
        UNCOLLECTIBLE = 'uncollectible', 'Incobrable'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Número de factura legible (para mostrar al usuario)
    invoice_number = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Número de factura para display (ej: INV-2026-00001)"
    )
    
    # Relaciones
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices'
    )
    
    # AGNÓSTICO
    external_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        db_index=True
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    
    # Montos
    # IMPORTANTE: Todos en Decimal, nunca float
    currency = models.CharField(max_length=3, default='MXN')
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="IVA u otros impuestos"
    )
    discount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Descuentos aplicados (cupones, etc.)"
    )
    total = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    amount_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monto efectivamente pagado"
    )
    amount_due = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monto pendiente de pago"
    )
    
    # Fechas
    invoice_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Fecha límite de pago"
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Periodo que cubre esta factura
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    
    # Datos de facturación (snapshot al momento de la factura)
    billing_name = models.CharField(max_length=200, blank=True, default="")
    billing_email = models.EmailField(blank=True, default="")
    billing_address = models.JSONField(default=dict, blank=True)
    
    # PDF de la factura (URL o path)
    pdf_url = models.URLField(max_length=500, blank=True, default="")
    
    # Notas
    notes = models.TextField(blank=True, default="")
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_invoices'
        ordering = ['-invoice_date']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['external_id']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.total} {self.currency} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Auto-calcular amount_due
        self.amount_due = self.total - self.amount_paid
        super().save(*args, **kwargs)
    
    @property
    def is_paid(self):
        return self.status == self.Status.PAID


# =============================================================================
# INVOICE ITEM - Líneas de Factura
# =============================================================================
class InvoiceItem(models.Model):
    """
    Líneas de detalle dentro de una factura.
    
    Permite desglosar:
    - Cargo por suscripción
    - Proration (cambio de plan a mitad de ciclo)
    - Cargos adicionales
    - Descuentos aplicados
    """
    
    class ItemType(models.TextChoices):
        SUBSCRIPTION = 'subscription', 'Suscripción'
        PRORATION = 'proration', 'Prorrateo'
        ONE_TIME = 'one_time', 'Cargo Único'
        DISCOUNT = 'discount', 'Descuento'
        TAX = 'tax', 'Impuesto'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    description = models.CharField(max_length=500)
    
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="quantity * unit_price"
    )
    
    # Referencia al plan (si aplica)
    plan = models.ForeignKey(
        Plan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Periodo que cubre este item
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_invoice_items'

    def __str__(self):
        return f"{self.description}: {self.amount}"
    
    def save(self, *args, **kwargs):
        # Auto-calcular amount
        self.amount = self.quantity * self.unit_price
        super().save(*args, **kwargs)


# =============================================================================
# PAYMENT - Intentos de Pago
# =============================================================================
class Payment(models.Model):
    """
    Registra cada intento de cobro (exitoso o fallido).
    
    IMPORTANTE:
    - Una Invoice puede tener múltiples Payments (reintentos)
    - Solo el último exitoso marca la factura como pagada
    - Los fallidos se guardan para debugging y analytics
    
    DISEÑO AGNÓSTICO:
    - 'external_id' mapea a PaymentIntent (Stripe), Charge, etc.
    - 'failure_code' usa códigos genéricos que luego se mapean por pasarela
    """
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        PROCESSING = 'processing', 'Procesando'
        SUCCEEDED = 'succeeded', 'Exitoso'
        FAILED = 'failed', 'Fallido'
        CANCELED = 'canceled', 'Cancelado'
        REFUNDED = 'refunded', 'Reembolsado'
        PARTIALLY_REFUNDED = 'partially_refunded', 'Reembolso Parcial'
    
    class FailureReason(models.TextChoices):
        """Razones de fallo genéricas (mapear desde cada pasarela)."""
        INSUFFICIENT_FUNDS = 'insufficient_funds', 'Fondos Insuficientes'
        CARD_DECLINED = 'card_declined', 'Tarjeta Rechazada'
        EXPIRED_CARD = 'expired_card', 'Tarjeta Expirada'
        INCORRECT_CVC = 'incorrect_cvc', 'CVC Incorrecto'
        PROCESSING_ERROR = 'processing_error', 'Error de Procesamiento'
        FRAUD_DETECTED = 'fraud_detected', 'Fraude Detectado'
        AUTHENTICATION_REQUIRED = 'authentication_required', '3DS Requerido'
        LIMIT_EXCEEDED = 'limit_exceeded', 'Límite Excedido'
        OTHER = 'other', 'Otro'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relaciones
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    
    # AGNÓSTICO
    provider = models.CharField(max_length=30)  # stripe, paypal, etc.
    external_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        db_index=True,
        help_text="ID del pago en pasarela (ej: pi_xxxx, ch_xxxx)"
    )
    
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    # Montos
    currency = models.CharField(max_length=3, default='MXN')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_refunded = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Fee de la pasarela (para reportes)
    fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Comisión cobrada por la pasarela"
    )
    
    # Información de fallo
    failure_reason = models.CharField(
        max_length=50,
        choices=FailureReason.choices,
        null=True,
        blank=True
    )
    failure_message = models.TextField(
        blank=True, 
        default="",
        help_text="Mensaje de error de la pasarela"
    )
    
    # Número de intento (para reintentos)
    attempt_number = models.PositiveSmallIntegerField(default=1)
    
    # Fechas
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Receipt (recibo)
    receipt_url = models.URLField(max_length=500, blank=True, default="")
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice', 'status']),
            models.Index(fields=['external_id']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency} ({self.status})"
    
    @property
    def is_successful(self):
        return self.status == self.Status.SUCCEEDED
    
    @property
    def net_amount(self):
        """Monto neto después de fees y reembolsos."""
        return self.amount - self.fee - self.amount_refunded


# =============================================================================
# COUPON & DISCOUNT - Sistema de Cupones
# =============================================================================
class Coupon(models.Model):
    """
    Define cupones de descuento.
    
    TIPOS:
    - Porcentaje: 20% off
    - Monto fijo: $100 MXN off
    
    DURACIÓN:
    - once: Solo el primer pago
    - repeating: Por X meses
    - forever: Para siempre mientras tenga suscripción
    """
    
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Porcentaje'
        FIXED_AMOUNT = 'fixed_amount', 'Monto Fijo'
    
    class Duration(models.TextChoices):
        ONCE = 'once', 'Una Vez'
        REPEATING = 'repeating', 'Repetitivo'
        FOREVER = 'forever', 'Para Siempre'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Código que el usuario ingresa
    code = models.CharField(max_length=50, unique=True, db_index=True)
    
    # AGNÓSTICO
    external_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Configuración del descuento
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Porcentaje (ej: 20.00) o monto fijo"
    )
    currency = models.CharField(
        max_length=3, 
        default='MXN',
        help_text="Solo aplica si es fixed_amount"
    )
    
    # Duración del descuento
    duration = models.CharField(max_length=20, choices=Duration.choices)
    duration_in_months = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Solo si duration='repeating'"
    )
    
    # Restricciones
    max_redemptions = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Usos máximos totales (null = ilimitado)"
    )
    times_redeemed = models.PositiveIntegerField(default=0)
    
    # Validez
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    
    # Planes aplicables (vacío = todos)
    applicable_plans = models.ManyToManyField(
        Plan, 
        blank=True,
        related_name='coupons'
    )
    
    is_active = models.BooleanField(default=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_coupons'

    def __str__(self):
        if self.discount_type == self.DiscountType.PERCENTAGE:
            return f"{self.code}: {self.amount}% off"
        return f"{self.code}: {self.amount} {self.currency} off"
    
    @property
    def is_valid(self):
        """¿El cupón es válido ahora?"""
        if not self.is_active:
            return False
        now = timezone.now()
        if now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_redemptions and self.times_redeemed >= self.max_redemptions:
            return False
        return True


class Discount(models.Model):
    """
    Instancia de un cupón aplicado a una suscripción específica.
    
    Un Coupon puede generar múltiples Discounts (uno por cada uso).
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name='discounts'
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='discounts'
    )
    
    # Tracking de uso
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Cuando expira el descuento"
    )
    
    # Para duration='repeating'
    remaining_months = models.PositiveIntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_discounts'

    def __str__(self):
        return f"{self.coupon.code} on {self.subscription}"


# =============================================================================
# USAGE RECORD - Tracking de Uso (Para Límites por Plan)
# =============================================================================
class UsageRecord(models.Model):
    """
    Registra el uso de features limitadas por plan.
    
    EJEMPLO:
    - Plan Free permite 3 grupos → Registrar cada grupo creado
    - Verificar contra PlanFeature antes de permitir crear más
    
    ÚTIL PARA:
    - Mostrar "Has usado 2 de 3 grupos"
    - Bloquear acciones cuando se alcanza el límite
    - Analytics de uso por plan
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='usage_records'
    )
    
    # Feature key (debe coincidir con PlanFeature.feature_key)
    feature_key = models.CharField(max_length=100)
    
    # Cantidad usada
    quantity = models.PositiveIntegerField(default=1)
    
    # Periodo de medición (para features que se resetean mensualmente)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_usage_records'
        indexes = [
            models.Index(fields=['subscription', 'feature_key', 'period_start']),
        ]

    def __str__(self):
        return f"{self.subscription.user}: {self.feature_key} = {self.quantity}"


# =============================================================================
# WEBHOOK LOG - Auditoría de Webhooks (Muy Importante)
# =============================================================================
class WebhookLog(models.Model):
    """
    Registra todos los webhooks recibidos de pasarelas de pago.
    
    CRÍTICO PARA:
    - Debugging cuando algo falla
    - Idempotencia (evitar procesar el mismo evento 2 veces)
    - Auditoría y compliance
    
    FLUJO:
    1. Llega webhook de Stripe/PayPal
    2. Se guarda en WebhookLog con status='received'
    3. Se procesa → status='processed' o 'failed'
    4. Si falla, se puede reintentar manualmente
    """
    
    class Status(models.TextChoices):
        RECEIVED = 'received', 'Recibido'
        PROCESSING = 'processing', 'Procesando'
        PROCESSED = 'processed', 'Procesado'
        FAILED = 'failed', 'Fallido'
        IGNORED = 'ignored', 'Ignorado'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Identificación
    provider = models.CharField(max_length=30)  # stripe, paypal, etc.
    event_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="ID del evento en la pasarela (para idempotencia)"
    )
    event_type = models.CharField(
        max_length=100,
        help_text="Tipo de evento (ej: invoice.payment_succeeded)"
    )
    
    # Payload completo (para debugging)
    payload = models.JSONField()
    
    # Headers HTTP (para verificación de firma)
    headers = models.JSONField(default=dict, blank=True)
    
    # Estado de procesamiento
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED
    )
    
    # Si falló, guardar el error
    error_message = models.TextField(blank=True, default="")
    
    # Tracking
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_attempts = models.PositiveSmallIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_webhook_logs'
        indexes = [
            models.Index(fields=['provider', 'event_id']),
            models.Index(fields=['event_type', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.provider}:{self.event_type} ({self.status})"
