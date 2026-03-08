from django_filters import rest_framework as filters
from .models import Event, Location

class EventFilter(filters.FilterSet):
    start_date_from = filters.DateTimeFilter(field_name='start_date', lookup_expr='gte')
    start_date_to = filters.DateTimeFilter(field_name="start_date", lookup_expr='lte')

    end_date_from = filters.DateTimeFilter(field_name="end_date", lookup_expr='gte')
    end_date_to = filters.DateTimeFilter(field_name="end_date", lookup_expr='lte')

    rating_from = filters.NumberFilter(field_name="rating", lookup_expr='gte')
    rating_to = filters.NumberFilter(field_name="rating", lookup_expr='lte')

    location = filters.ModelMultipleChoiceFilter(
        queryset=Location.objects.all(),
        field_name='location',
    )

    class Meta:
        model = Event
        fields = ['start_date_from', 'start_date_to', 'end_date_from', 'end_date_to', 'rating_from', 'rating_to', 'location']