from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import EventViewSet, LocationViewSet

# Роутер для всех стандартных действий CRUD
router = SimpleRouter()
router.register(r"locations", LocationViewSet, basename="location")
router.register(r"events", EventViewSet, basename="event")

urlpatterns = [
    path("", include(router.urls)),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
