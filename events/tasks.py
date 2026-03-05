from celery import shared_task
from .models import Location, WeatherData
from .services import get_weather_for_coordinates

@shared_task
def update_all_locations_weather():
    """
    Периодическая задача для обновления погоды во всех локациях
    """
    locations = Location.objects.all()
    for loc in locations:
        weather_info = get_weather_for_coordinates(loc.latitude, loc.longitude)

        if weather_info:
            # Обновляем существующую запись или создаем новую для этой локации
            WeatherData.objects.update_or_create(
                location=loc,
                defaults={
                    'temperature': weather_info['temperature'],
                    'humidity': weather_info['humidity'],
                    'pressure': weather_info['pressure'],
                    'wind_speed': weather_info['wind_speed'],
                    'wind_direction': weather_info['wind_direction'],
                }
            )