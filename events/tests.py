import tempfile

from datetime import datetime
from io import BytesIO

from PIL import Image

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Event, EventImage, Location, WeatherData
from .serializers import WeatherDataSerializer


class EventLogicTest(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="admin", password="password")
        self.location = Location.objects.create(
            name="Красноярск", latitude=56.010543, longitude=92.852581
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, MEDIA_ROOT=tempfile.gettempdir())
    def test_image_thumbnail_resize(self):
        """
        Проверка автоматического ресайза превью до 200 пикселей
        """
        tz = timezone.get_current_timezone()
        dt_kwargs = {
            "pub_date": datetime(2026, 1, 1, 10, 0, tzinfo=tz),
            "start_date": datetime(2026, 1, 1, 12, 0, tzinfo=tz),
            "end_date": datetime(2026, 1, 1, 14, 0, tzinfo=tz),
        }

        event = Event.objects.create(
            title="Test Event", location=self.location, author=self.user, **dt_kwargs
        )

        bts = BytesIO()
        img = Image.new("RGB", (500, 1000), color="red")
        img.save(bts, format="JPEG")

        uploaded_file = SimpleUploadedFile(
            name="test_image.jpg", content=bts.getvalue(), content_type="image/jpeg"
        )

        EventImage.objects.create(event=event, image=uploaded_file)
        event.refresh_from_db()

        self.assertIsNotNone(event.thumbnail)
        with Image.open(event.thumbnail.path) as thumb:
            self.assertEqual(min(thumb.size), 200)

    def test_pressure_conversion(self):
        """
        Проверка конвертации давления в мм. рт. ст.
        """
        weather = WeatherData.objects.create(
            location=self.location,
            temperature=20.0,
            humidity=50,
            pressure=1000.0,
            wind_speed=2.0,
            wind_direction="North",
        )
        expected_mmhg = round(1000.0 * 0.75006, 1)
        serializer = WeatherDataSerializer(weather)
        self.assertEqual(serializer.data["pressure_mmhg"], expected_mmhg)


class EventAPITest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@mail.ru", "pass")
        self.user = User.objects.create_user("user", "user@mail.ru", "pass")
        self.location = Location.objects.create(
            name="Дивногорск", latitude=55.957726, longitude=92.380148
        )

        tz = timezone.get_current_timezone()
        aware_dt = datetime(2026, 1, 1, 10, 0, tzinfo=tz)

        # Публичное мероприятие
        Event.objects.create(
            title="Public",
            status="published",
            author=self.admin,
            location=self.location,
            pub_date=aware_dt,
            start_date=aware_dt,
            end_date=aware_dt,
        )
        # Черновик
        Event.objects.create(
            title="Draft",
            status="draft",
            author=self.admin,
            location=self.location,
            pub_date=aware_dt,
            start_date=aware_dt,
            end_date=aware_dt,
        )

    def test_anonymous_user_visibility(self):
        """
        Обычный пользователь видит только опубликованные записи
        """
        url = reverse("event-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Public")

    def test_admin_visibility(self):
        """
        Администратор видит всё (и черновики, и опубликованные)
        """
        self.client.force_authenticate(user=self.admin)
        url = reverse("event-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)
