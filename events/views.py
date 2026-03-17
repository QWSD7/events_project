import logging

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import EventFilter
from .models import Event, Location, WeatherData
from .permissions import IsAdminOrReadOnly, IsSuperUser
from .serializers import EventSerializer, LocationSerializer
from .tasks import (
    export_events_to_xlsx_task,
    import_events_from_xlsx_task,
    update_single_location_weather,
)

logger = logging.getLogger(__name__)

class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsSuperUser]

    # Поиск по названию места для связи с тех. заданием
    search_fields = ["name"]
    filter_backends = [filters.SearchFilter]


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAdminOrReadOnly]

    # Конфигурация фильтров и поиска
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]

    # Фильтрация по тех. заданию: Диапазоны дат, места и рейтинг
    filterset_class = EventFilter

    # Поиск по названию мероприятия или по названию места
    search_fields = ["title", "location__name"]

    # Сортировка по тех. заданию
    ordering_fields = ["title", "start_date", "end_date"]
    ordering = ["title"]  # Стандартная сортировка по названию

    def get_queryset(self):
        """
        Логика доступа по тех. заданию:
        - Суперпользователь видит всё.
        - Остальные - только опубликованные.
        """
        # Предзагружаем только последнюю погоду, чтобы не тянуть всю историю
        latest_weather = WeatherData.objects.order_by("-updated_at")

        base_qs = Event.objects.select_related("location", "author").prefetch_related(
            "images",
            Prefetch("location__weather", queryset=latest_weather, to_attr="latest_weather_cache"),
        )

        if self.request.user.is_superuser:
            return base_qs
        return base_qs.filter(status="published")

    def perform_create(self, serializer):
        event = serializer.save(author=self.request.user)
        update_single_location_weather.delay(event.location.id)

    @action(detail=False, methods=["get"], permission_classes=[IsSuperUser])
    def export_xlsx(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        event_ids = list(queryset.values_list("id", flat=True))

        if not event_ids:
            return Response({"error": "Нет данных для экспорта"}, status=400)

            # Запускаем фоновую задачу
        export_events_to_xlsx_task.delay(event_ids, request.user.id)

        logging.info(f"Экспорт {len(event_ids)} записей запущен.")

        return Response(
            {
                "message": f"Экспорт {len(event_ids)} записей запущен. "
                f"Файл будет доступен в папке экспорта."
            }
        )


    @action(detail=False, methods=["post"], permission_classes=[IsSuperUser])
    def import_xlsx(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "Файл не предоставлен"}, status=status.HTTP_400_BAD_REQUEST)

        # Сохраняем файл временно, так как Celery не может получить доступ к файлу из памяти
        from django.core.files.storage import default_storage

        filename = default_storage.save(f"imports/{file.name}", file)
        file_path = default_storage.path(filename)

        # Запускаем задачу
        import_events_from_xlsx_task.delay(file_path, request.user.id)

        logging.info(f"Импорт запущен в фоновом режиме.")

        return Response({"message": "Импорт запущен в фоновом режиме."})
