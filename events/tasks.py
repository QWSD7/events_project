import logging
import os
from io import BytesIO

import requests
from celery import shared_task
from PIL import Image

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import EmailSettings, Event, Location, WeatherData
from .utils import get_weather_for_coordinates

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(requests.RequestException,),  # Авто-повтор при сбоях сети
    retry_backoff=True,
    max_retries=3,
)
def update_single_location_weather(self, location_id):
    """
    Задача для обновления в одной конкретной локации
    """
    try:
        loc = Location.objects.get(id=location_id)
        logger.info(f"Выбор погоды для конкретного местоположения: {loc.name} (ID: {location_id})")

        weather_info = get_weather_for_coordinates(loc.latitude, loc.longitude)

        if weather_info:
            WeatherData.objects.create(
                location=loc,
                temperature=weather_info["temperature"],
                humidity=weather_info["humidity"],
                pressure=weather_info["pressure"],
                wind_speed=weather_info["wind_speed"],
                wind_direction=weather_info["wind_direction"],
            )
            return f"Погода обновлена для: {loc.name}"
        logger.warning(
            f"Weather API вернул пустые данные для указанного местоположения {location_id}"
        )
        return "No data"
    except Location.DoesNotExist:
        logger.error(f"Местоположение с идентификатором {location_id} не найдено в базе данных")
        return f"Место {location_id} не найдено"
    except Exception as exc:
        # Логируем ошибку с трейсбэком
        logger.exception(f"Непредвиденная ошибка при обновлении погоды: {exc}")
        raise  # Важно пробросить ошибку для autoretry


@shared_task
def update_all_locations_weather():
    """
    Периодическая задача для запуска небольших задач
    """
    location_ids = Location.objects.values_list("id", flat=True)
    for loc_id in location_ids:
        update_single_location_weather.delay(loc_id)


@shared_task
def publish_and_notify_scheduled_events():
    now = timezone.now()

    with transaction.atomic():
        events_to_publish = Event.objects.select_for_update(skip_locked=True).filter(
            status="draft", pub_date__lte=now
        )

        count = events_to_publish.count()  # Считаем заранее для лога

        if count > 0:
            for event in events_to_publish:
                event.status = "published"
                event.save()

            # Используем f-строку для информативности
            logger.info(f"Успешно опубликовано: {count} мероприятий.")
        else:
            # Необязательно, но полезно для отладки периодических задач
            logger.debug("Мероприятий для публикации нету")

    return f"Опубликовано {count} мероприятий."


@shared_task(
    bind=True,
    autoretry_for=(requests.RequestException,),  # Авто-повтор при сбоях сети
    retry_backoff=True,
    max_retries=3,
)
def send_publication_email_task(self, weather_update_result, event_id):
    logger.info(f"Задача рассылки запущена. Результат задачи погоды: {weather_update_result}")
    try:
        event = Event.objects.get(id=event_id)
        event.refresh_from_db()
        mail_settings = EmailSettings.load()
        recipients = mail_settings.get_recipient_list()

        if not recipients:
            return "No recipients found"

        # Безопасное форматирование строк
        context = {
            "title": event.title,
            "location": event.location.name,
            "start_date": event.start_date.strftime("%d.%m.%Y %H:%M"),
            "weather": event.get_weather_report(),
        }

        subject = mail_settings.subject_template.format_map(context)
        message = mail_settings.message_template.format_map(context)

        from django.conf import settings
        from django.core.mail import send_mail

        send_mail(subject, message, settings.EMAIL_HOST_USER, recipients)
        logger.info(f"Электронное письмо о мероприятии отправлено: {event_id}")
    except Exception as e:
        logger.exception(f"Ошибка отправки почты: {str(e)}")
        raise


@shared_task(
    bind=True,
    autoretry_for=(OSError,),  # Ошибки ввода-вывода часто временные (проблемы с хранилищем)
    retry_backoff=True,
    max_retries=3,
)
def generate_event_thumbnail_task(self, event_id, image_id):
    """
    Асинхронная генерация превью для мероприятия.
    """
    from .models import Event, EventImage  # Локальный импорт против циклов

    try:
        logger.info(
            f"Запуск создания превью для мероприятия: {event_id} "
            f"Используется изображение: {image_id}"
        )
        event = Event.objects.get(pk=event_id)
        image_obj = EventImage.objects.get(pk=image_id)

        if not image_obj.image:
            logger.warning(f"Нет изображения для мероприятия {image_id}")
            return "Не найден файл"

        try:
            img = Image.open(image_obj.image.path)
        except FileNotFoundError as e:
            logger.error(f"Файл изображения не найден по пути: {image_obj.image.path}")
            raise e

        # Открываем изображение через путь (path)
        with img:
            img_format = img.format or "JPEG"

            # Расчёт: уменьшаем фото до 200px по наименьшей стороне (согласно тех. заданию)
            width, height = img.size
            if width < height:
                new_width = 200
                new_height = int(height * (200 / width))
            else:
                new_height = 200
                new_width = int(width * (200 / height))

            # логирование для отладки (уровень DEBUG, чтобы не спамить в продакшене)
            logger.debug(
                f"Изображение {image_id} преобразилось "
                f"из {width}x{height} в {new_width}x{new_height}"
            )

            img = img.resize((new_width, new_height), Image.LANCZOS)

            # Сохраняем в память
            thumb_io = BytesIO()
            img.save(thumb_io, format=img_format, quality=85)

            # Сохраняем результат в связанную модель Event
            filename = os.path.basename(image_obj.image.name)
            event.thumbnail.save(
                filename,
                ContentFile(thumb_io.getvalue()),
                save=False,  # Не вызываем save() всего объекта пока что
            )
            # Обновляем только поле превью
            event.save(update_fields=["thumbnail"])

        logger.info(f"Превью создано для мероприятия {event_id}")
        return f"Превью создано для мероприятия {event_id}"

    except (Event.DoesNotExist, EventImage.DoesNotExist) as e:
        logger.error(f"Отсутствуют объекты базы данных: {str(e)}")
        return "Objects not found"
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при создании превью мероприятия {event_id}: {str(e)}")
        raise e


@shared_task
def export_events_to_xlsx_task(event_ids, user_id):
    from .services import export_events_to_xlsx

    logger.info(f"Начало фонового экспорта для пользователя {user_id}")

    try:
        # Получаем объекты по списку ID
        queryset = Event.objects.filter(id__in=event_ids).select_related("location")

        # Генерируем контент файла (BytesIO) через наш сервис
        output = export_events_to_xlsx(queryset)

        # Генерируем имя файла
        now = timezone.localtime(timezone.now()).strftime("%Y-%m-%d_%H-%M")
        filename = f"export_{now}_{user_id}.xlsx"

        # Путь сохранения
        relative_path = os.path.join("exports", filename)
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Записываем на диск
        with open(full_path, "wb") as f:
            f.write(output.getbuffer())

        logger.info(f"Экспорт завершен. Файл сохранен: {full_path}")

        return f"Файл создан: {relative_path}"

    except Exception as e:
        logger.exception("Ошибка в фоновой задаче экспорта")
        raise e


@shared_task
def import_events_from_xlsx_task(file_path, user_id):
    from django.contrib.auth.models import User

    from .services import import_events_from_xlsx

    user = User.objects.get(id=user_id)
    try:
        # Открываем файл по пути
        with open(file_path, "rb") as f:
            count = import_events_from_xlsx(f, user)

        logger.info(f"Фоновый импорт завершен: {count} записей.")
        # Тут можно отправить уведомление пользователю (через WebSocket или Email)
    finally:
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)
