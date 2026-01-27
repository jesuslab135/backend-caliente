import logging
from rest_framework import viewsets
from api.models import Subscription
from api.Serializers.subscription_serializer import SubscriptionSerializer
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api')

@extend_schema(tags=['Subscriptions'])
class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet para Subscriptions.
    Logging: create, update, destroy (CRÍTICO - todas las operaciones de billing)
    """
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer

    def create(self, request, *args, **kwargs):
        logger.info(
            f"[BILLING-CRITICAL] Intento de CREATE en Subscription | "
            f"Usuario: {request.user} | User_ID: {request.data.get('user')} | "
            f"Plan_ID: {request.data.get('plan')}"
        )
        try:
            response = super().create(request, *args, **kwargs)
            logger.info(
                f"[BILLING-CRITICAL] Subscription CREATE exitoso. "
                f"ID: {response.data.get('id')} | User: {response.data.get('user')} | "
                f"Plan: {response.data.get('plan')} | Status: {response.data.get('status')}"
            )
            return response
        except Exception as e:
            logger.error(f"[BILLING-CRITICAL] Error en CREATE de Subscription: {str(e)}")
            raise e

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_status = instance.status
        old_plan = instance.plan_id
        logger.info(
            f"[BILLING-CRITICAL] Intento de UPDATE en Subscription | "
            f"Usuario: {request.user} | ID: {instance.id} | "
            f"Status actual: {old_status} | Plan actual: {old_plan} | "
            f"Campos modificados: {list(request.data.keys())}"
        )
        try:
            response = super().update(request, *args, **kwargs)
            logger.info(
                f"[BILLING-CRITICAL] Subscription UPDATE exitoso. ID: {response.data.get('id')} | "
                f"Status: {old_status} → {response.data.get('status')} | "
                f"Plan: {old_plan} → {response.data.get('plan')}"
            )
            return response
        except Exception as e:
            logger.error(
                f"[BILLING-CRITICAL] Error en UPDATE de Subscription ID={instance.id}: {str(e)}"
            )
            raise e

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        logger.warning(
            f"[BILLING-CRITICAL] Intento de DESTROY en Subscription | "
            f"Usuario: {request.user} | ID: {instance.id} | "
            f"User: {instance.user_id} | Plan: {instance.plan_id} | "
            f"Status: {instance.status}"
        )
        try:
            response = super().destroy(request, *args, **kwargs)
            logger.warning(
                f"[BILLING-CRITICAL] Subscription DESTROY exitoso. ID: {instance.id}"
            )
            return response
        except Exception as e:
            logger.error(
                f"[BILLING-CRITICAL] Error en DESTROY de Subscription ID={instance.id}: {str(e)}"
            )
            raise e
