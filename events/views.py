from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch
from django.http import FileResponse
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import EventFilter
from .models import Event, Location, WeatherData
from .permissions import IsAdminOrReadOnly, IsSuperUser
from .serializers import EventSerializer, LocationSerializer
from .services import export_events_to_xlsx, import_events_from_xlsx
from .tasks import update_single_location_weather


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
        queryset = self.get_queryset()
        filtered_queryset = self.filter_queryset(queryset)

        file_handle = export_events_to_xlsx(filtered_queryset)

        now = timezone.localtime(timezone.now())

        time_str = now.strftime("%Y-%m-%d_%H-%M")

        filename = f"events_{time_str}.xlsx"
        return FileResponse(file_handle, as_attachment=True, filename=filename)

    @action(detail=False, methods=["post"], permission_classes=[IsSuperUser])
    def import_xlsx(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "Файл не предоставлен"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            count = import_events_from_xlsx(file, request.user)
            return Response(
                {"message": f"Успешно импортировано: {count}"}, status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {"error": f"Ошибка при импорте: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST
            )
