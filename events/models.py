from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from PIL import Image
import os
from io import BytesIO
from django.core.files.base import ContentFile


class Location(models.Model):
    name = models.CharField("Название места", max_length=255)
    latitude = models.FloatField("Широта")
    longitude = models.FloatField("Долгота")

    def __str__(self):
        return self.name


class WeatherData(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='weather')
    temperature = models.FloatField("Температура (°C)", editable=False)
    humidity = models.PositiveIntegerField("Влажность (%)", editable=False)
    pressure = models.FloatField("Давление (мм рт. ст.)", editable=False)
    wind_direction = models.CharField("Направление ветра", max_length=50, editable=False)
    wind_speed = models.FloatField("Скорость ветра (м/с)", editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Данные погоды"


class Event(models.Model):
    STATUS_CHOSES = [
        ('draft', 'Черновик'),
        ('published', 'Опубликовано'),
    ]

    title = models.CharField("Название", max_length=255)
    description = models.TextField("Описание")
    pub_date = models.DateTimeField("Дата и время публикации")
    start_date = models.DateTimeField("Дата и время начала")
    end_date = models.DateTimeField("Дата и время завершения")
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Автор")
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='events',
                                 verbose_name="Место проведения")
    rating = models.PositiveIntegerField("Рейтинг", validators=[MinValueValidator(0), MaxValueValidator(25)], default=0)
    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOSES, default='draft')

    # Поле для превью, сжатые фото (заполняется автоматически)
    thumbnail = models.ImageField("Превью", upload_to='thumbnails/', editable=False, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Проверяем, меняется ли статус на 'published'
        old_status = None
        if self.pk:
            old_status = Event.objects.filter(pk=self.pk).values_list('status', flat=True).first()

        super().save(*args, **kwargs)

        # Если статус стал published (и раньше был другим), ставим задачу в очередь
        if self.status == 'published' and old_status != 'published':
            # transaction.on_commit гарантирует, что задача уйдет в Celery
            # только после того, как данные РЕАЛЬНО запишутся в БД
            from .tasks import send_publication_email_task
            transaction.on_commit(lambda: send_publication_email_task.delay(self.id))

    def get_weather_report(self):
        """
        Выносим формирование отчета в модель
        """
        weather = self.location.weather.order_by('-updated_at').first()
        if not weather:
            return "Нет данных о погоде"
        return f"\n\nПрогноз погоды:\nТемпература: {weather.temperature}°C\nВлажность: {weather.humidity}%\nДавление (мм. рт. ст.): {weather.pressure}\nНаправление ветра: {weather.wind_direction}\nСкорость ветра: {weather.wind_speed}"

    class Meta:
        # сортировка по алфавиту
        ordering = ['title']

    def __str__(self):
        return self.title


class EventImage(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField("Изображение", upload_to="events/")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and self.image and not self.event.thumbnail:
            self.generate_event_thumbnail()

    def generate_event_thumbnail(self):
        img = Image.open(self.image)
        img_format = img.format

        # Расчёт: уменьшаем фото до 200px по наименьшей стороне (согласно тех. заданию)
        width, height = img.size
        if width < height:
            new_width = 200
            new_height = int(height * (200 / width))
        else:
            new_height = 200
            new_width = int(width * (200 / height))

        img = img.resize((new_width, new_height), Image.LANCZOS)

        thumb_io = BytesIO()
        img.save(thumb_io, format=img_format, quality=85)

        filename = os.path.basename(self.image.name)
        self.event.thumbnail.save(filename, ContentFile(thumb_io.getvalue()), save=True)


class EmailSettings(models.Model):
    subject_template = models.CharField("Тема письма", max_length=255, default="Новое мероприятие")
    message_template = models.TextField(
        "Текст письма",
        default="Здравствуйте!\n\nОпубликовано событие: {title}\nМесто: {location}\nДата начала: {start_date}\n{weather}\n\nЖдем вас!"
    )
    recipients_text = models.TextField(
        "Список адресатов",
        help_text="Введите email-адреса через запятую или с новой строки",
        default="admin@example.com"
    )

    class Meta:
        verbose_name = "Настройки уведомлений"
        verbose_name_plural = "Настройки уведомлений"

    def get_recipient_list(self):
        """Превращает текст из поля в чистый список [email, email]"""
        import re
        # Регулярка найдет все, что похоже на email, игнорируя пробелы и запятые
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', self.recipients_text)
        return list(set(emails))

    @classmethod
    def load(cls):
        # Пытаемся взять первую запись, если нет — создаем дефолтную
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return "Настройки рассылки"
