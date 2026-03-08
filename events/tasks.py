from .models import Location, WeatherData, Event, EmailSettings
from .utils import get_weather_for_coordinates
from django.utils import timezone
from django.db import transaction
from celery import shared_task


@shared_task
def update_single_location_weather(location_id):
    """
    Задача для обновления в одной конкретной локации
    """
    try:
        loc = Location.objects.get(id=location_id)
        weather_info = get_weather_for_coordinates(loc.latitude, loc.longitude)

        if weather_info:
            WeatherData.objects.create(
                location=loc,
                temperature = weather_info['temperature'],
                humidity = weather_info['humidity'],
                pressure = weather_info['pressure'],
                wind_speed = weather_info['wind_speed'],
                wind_direction = weather_info['wind_direction'],
            )
            return f"Погода обновлена для: {loc.name}"
    except Location.DoesNotExist:
        return f"Место {location_id} не найдено"


@shared_task
def update_all_locations_weather():
    """
    Периодическая задача для запуска небольших задач
    """
    location_ids=Location.objects.values_list('id', flat=True)
    for loc_id in location_ids:
        update_single_location_weather.delay(loc_id)


@shared_task
def publish_and_notify_scheduled_events():
    now = timezone.now()

    with transaction.atomic():
        events_to_publish = Event.objects.select_for_update(skip_locked=True).filter(
            status='draft',
            pub_date__lte=now
        )

        count = 0
        for event in events_to_publish:
            event.status = 'published'
            event.save()
            count += 1

    return f"Запланированная публикация: {count} мероприятий."


@shared_task
def send_publication_email_task(event_id):
    try:
        event = Event.objects.get(id=event_id)
        update_single_location_weather(event.location.id)
        event.refresh_from_db()
        mail_settings = EmailSettings.load()
        recipients = mail_settings.get_recipient_list()

        if not recipients:
            return "No recipients found"

        # Безопасное форматирование строк
        context = {
            'title': event.title,
            'location': event.location.name,
            'start_date': event.start_date.strftime('%d.%m.%Y %H:%M'),
            'weather': event.get_weather_report()
        }

        subject = mail_settings.subject_template.format_map(context)
        message = mail_settings.message_template.format_map(context)

        from django.core.mail import send_mail
        from django.conf import settings

        send_mail(subject, message, settings.EMAIL_HOST_USER, recipients)
    except Exception as e:
        return f"Error sending mail: {str(e)}"
