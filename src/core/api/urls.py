from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api import Viewsets
from utils.router_utils import register_all_viewsets

router = DefaultRouter()

register_all_viewsets(router, Viewsets)

urlpatterns = [
    # Authentication endpoints (not auto-registered)
    path("auth/", include('api.urls_auth')),

    # Auto-registered model viewsets
    path("", include(router.urls)),
]