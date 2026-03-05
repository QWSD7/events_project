from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import EventViewSet, LocationViewSet

# Роутер для всех стандартных действий CRUD
router = SimpleRouter()
router.register(r'locations', LocationViewSet, basename='location')
router.register(r'events', EventViewSet, basename='event')

urlpatterns = [
    path('', include(router.urls)),
]