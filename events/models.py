from textwrap import dedent

from celery import chain

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction


class Location(models.Model):
    name = models.CharField("Название места", max_length=255)
    latitude = models.FloatField("Широта")
    longitude = models.FloatField("Долгота")

    def __str__(self):
        return self.name


class WeatherData(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="weather")
    temperature = models.FloatField("Температура (°C)", editable=False)
    humidity = models.PositiveIntegerField("Влажность (%)", editable=False)
    pressure = models.FloatField("Давление (мм рт. ст.)", editable=False)
    wind_direction = models.CharField("Направление ветра", max_length=50, editable=False)
    wind_speed = models.FloatField("Скорость ветра (м/с)", editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Данные погоды"
        verbose_name_plural = "Данные погоды"

    def __str__(self):
        # Возвращаем понятную строку
        return f"Погода для {self.location.name} ({self.updated_at.strftime('%d.%m %H:%M')})"


class Event(models.Model):
    STATUS_CHOSES = [
        ("draft", "Черновик"),
        ("published", "Опубликовано"),
    ]

    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание")
    pub_date = models.DateTimeField("Дата и время публикации")
    start_date = models.DateTimeField("Дата и время начала")
    end_date = models.DateTimeField("Дата и время завершения")
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Автор")
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="events", verbose_name="Место проведения"
    )
    rating = models.PositiveIntegerField(
        "Рейтинг", validators=[MinValueValidator(0), MaxValueValidator(25)], default=0
    )
    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOSES, default="draft")

    # Поле для превью, сжатые фото (заполняется автоматически)
    thumbnail = models.ImageField(
        "Превью", upload_to="thumbnails/", editable=False, null=True, blank=True
    )

    class Meta:
        # сортировка по алфавиту
        ordering = ["title"]
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Проверяем, меняется ли статус на 'published'
        old_status = None
        if self.pk:
            old_status = Event.objects.filter(pk=self.pk).values_list("status", flat=True).first()

        super().save(*args, **kwargs)

        # Если статус стал published (и раньше был другим), ставим задачу в очередь
        if self.status == "published" and old_status != "published":
            # transaction.on_commit гарантирует, что задача уйдет в Celery
            # только после того, как данные РЕАЛЬНО запишутся в БД
            from .tasks import send_publication_email_task, update_single_location_weather

            transaction.on_commit(
                lambda: chain(
                    # 1. Сначала обновляем погоду
                    update_single_location_weather.s(self.location.id),
                    # 2. Затем отправляем письмо (self.id — это id мероприятия)
                    send_publication_email_task.s(self.id),
                ).apply_async()
            )

    def get_weather_report(self):
        """
        Выносим формирование отчета в модель
        """
        weather = self.location.weather.order_by("-updated_at").first()
        if not weather:
            return "Нет данных о погоде"
        report = f"""
                Прогноз погоды:
                Температура: {weather.temperature}°C
                Влажность: {weather.humidity}%
                Давление (мм. рт. ст.): {weather.pressure}
                Направление ветра: {weather.wind_direction}
                Скорость ветра: {weather.wind_speed}
            """
        return dedent(report).strip()


class EventImage(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("Изображение", upload_to="events/")

    class Meta:
        verbose_name = "Изображение мероприятия"
        verbose_name_plural = "Изображения мероприятий"

    def __str__(self):
        # Возвращаем название мероприятия и имя файла
        return f"Изображение для {self.event.title} ({self.image.name})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and self.image and not self.event.thumbnail:
            from .tasks import generate_event_thumbnail_task

            # Используем on_commit, чтобы задача ушла в Celery
            # только после того, как запись EventImage реально сохранится в БД
            transaction.on_commit(
                lambda: generate_event_thumbnail_task.delay(self.event.id, self.id)
            )


def get_default_email_message():
    return dedent("""
        Здравствуйте!

        Опубликовано событие: {title}
        Место: {location}
        Дата начала: {start_date}
        {weather}

        Ждем вас!
    """).strip()


class EmailSettings(models.Model):
    subject_template = models.CharField("Тема письма", max_length=255, default="Новое мероприятие")
    message_template = models.TextField(
        "Текст письма",
        default=get_default_email_message,
    )

    recipients_text = models.TextField(
        "Список адресатов",
        help_text="Введите email-адреса через запятую или с новой строки",
        default="admin@example.com",
    )

    class Meta:
        verbose_name = "Настройки уведомлений"
        verbose_name_plural = "Настройки уведомлений"

    def __str__(self):
        return "Настройки рассылки"

    def get_recipient_list(self):
        """Превращает текст из поля в чистый список [email, email]"""
        import re

        # Регулярка найдет все, что похоже на email, игнорируя пробелы и запятые
        emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", self.recipients_text)
        return list(set(emails))

    @classmethod
    def load(cls):
        # Пытаемся взять первую запись, если нет — создаем дефолтную
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
