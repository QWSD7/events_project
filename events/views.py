from django.shortcuts import render
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Event, Location
from .serializers import EventSerializer, LocationSerializer
from .permissions import IsAdminOrReadOnly

class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes =  [IsAdminOrReadOnly]

    # Поиск по названию места для связи с тех. заданием
    search_fields = ['name']
    filter_backends = [filters.SearchFilter]

class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAdminOrReadOnly]

    # Конфигурация фильтров и поиска
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]

    # Фильтрация по тех. заданию: Диапазоны дат, места и рейтинг
    filterset_backends = {
        'starts_date': ['gte', 'lte'],
        'end_date': ['gte', 'lte'],
        'location': ['exact'],
        'rating': ['gte', 'lte'],
    }

    # Поиск по названию мероприятия или по названию места
    search_fields = ['title', 'location__name']

    # Сортировка по тех. заданию
    ordering_fields = ['title', 'start_date', 'end_date']
    ordering = ['title'] # Стандартная сортировка по названию

    def get_queryset(self):
        """
        Логика доступа по тех. заданию:
        - Суперпользователь видит всё.
        - Остальные - только опубликованные.
        """
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            return Event.objects.all()
        return Event.objects.filter(status='published')

    def perform_create(self, serializer):
        # При создании привязываем автора автоматически
        serializer.save(author=self.request.user)

