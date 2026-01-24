from django.urls import path, include
from rest_framework.routers import DefaultRouter

from api.Viewsets import group_viewset
from api.Viewsets import user_viewset
from api.Viewsets import profile_viewset
from api.Viewsets import blitz_viewset
from api.Viewsets import match_viewset
from api.Viewsets import chat_viewset
from api.Viewsets import message_viewset

router = DefaultRouter()

router.register(r'groups', group_viewset.GroupViewSet, basename='group')
router.register(r'users', user_viewset.UserViewSet, basename='user')
router.register(r'profiles', profile_viewset.ProfileViewSet, basename='profile')
router.register(r'blitzs', blitz_viewset.BlitzViewSet, basename='blitz')
router.register(r'matches', match_viewset.MatchViewSet, basename='match')
router.register(r'chats', chat_viewset.ChatViewSet, basename='chat')
router.register(r'messages', message_viewset.MessageViewSet, basename='message')

urlpatterns = [
    path("", include(router.urls)),
]