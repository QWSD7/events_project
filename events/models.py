from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from PIL import Image
import os
from io import BytesIO
from django.core.files.base import  ContentFile

class Location(models.Model):
    name = models.CharField("Название места", max_length=255)
    latitude = models.FloatField("Широта")
    longitude = models.FloatField("Долгота")

    def __str__(self):
        return self.name

class WeatherData(models.Model):
    location = models.OneToOneField(Location, on_delete=models.CASCADE, related_name='weather')
    temperature = models.FloatField("Температура (°C)")
    humidity = models.PositiveIntegerField("Влажность (%)")
    pressure = models.FloatField("Давление (мм рт. ст.)")
    wind_direction = models.CharField("Направление ветра", max_length=50)
    wind_speed = models.FloatField("Скорость ветра (м/с)")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Данные погоды"
        # запрещем редактирование через админку (согласно тех. заданию)
        managed = True

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
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='events', verbose_name="Место проведения")
    rating = models.PositiveIntegerField("Рейтинг", validators=[MinValueValidator(0), MaxValueValidator(25)], default=0)
    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOSES, default='draft')

    # Поле для превью, сжатые фото (заполняется автоматически)
    thumbnail = models.ImageField("Превью", upload_to='thumbnails/', editable=False, null=True, blank=True)

    class Meta:
        # сортировка по алфавиту
        ordering = ['title']

    def __str__(self):
        return self.title

class EventImage(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField("Изображение", upload_to="events/")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Сохранили основное фото, теперь генерируем фото-превью для мероприятия если его ещё нету
        if self.image and not self.event.thumbnail:
            self.make_thumbnail()

    def make_thumbnail(self):
        img = Image.open(self.image)

        # Расчёт: уменьшаем фото до 200px по наименьшей стороне (согласно тех. заданию)
        width, height = img.size
        assert_ratio = width / height

        if width < height:
            __new_width = 200
            new_width = int(__new_width / assert_ratio)
        else:
            __new_height = 200
            new_width = int(__new_height * assert_ratio)

        img.thumbnail((new_width, __new_height), Image.LANCZOS)

        thumb_io = BytesIO()
        img.save(thumb_io, img.format, quality=85)

        filename = os.path.basename(self.image.name)
        self.event.thumbnail.save(filename, ContentFile(thumb_io.getvalue()), save=True)
