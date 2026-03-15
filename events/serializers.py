from django.db import transaction
from rest_framework import serializers

from .models import Event, EventImage, Location, WeatherData


class WeatherDataSerializer(serializers.ModelSerializer):
    pressure_hpa = serializers.FloatField(source="pressure")
    pressure_mmhg = serializers.SerializerMethodField()

    class Meta:
        model = WeatherData
        fields = [
            "temperature",
            "humidity",
            "pressure_hpa",
            "pressure_mmhg",
            "wind_direction",
            "wind_speed",
            "updated_at",
        ]

    def get_pressure_mmhg(self, obj):
        if obj.pressure is not None:
            return round(obj.pressure * 0.75006, 1)
        return None


class LocationSerializer(serializers.ModelSerializer):
    actual_weather = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = ["id", "name", "latitude", "longitude", "actual_weather"]

    def get_actual_weather(self, obj):
        weathers = obj.weather.all()
        if weathers:
            latest = sorted(weathers, key=lambda x: x.updated_at, reverse=True)[0]
            return WeatherDataSerializer(latest).data
        return None


class EventImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventImage
        fields = ["id", "image"]


class EventSerializer(serializers.ModelSerializer):
    # Вложенный сериализатор для места проведения (только чтение)
    location_details = LocationSerializer(source="location", read_only=True)

    # Список всех изображений мероприятия
    images = EventImageSerializer(many=True, read_only=True)

    # Позволяем загружать файлы при создании
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "author",
            "location",
            "location_details",
            "images",
            "uploaded_images",
            "thumbnail",
            "pub_date",
            "start_date",
            "end_date",
            "rating",
            "status",
        ]
        read_only_fields = ["author", "thumbnail"]

    def create(self, validated_data):
        uploaded_images = validated_data.pop("uploaded_images", [])

        with transaction.atomic():
            event = Event.objects.create(**validated_data)

            if uploaded_images:
                image_objects = [EventImage(event=event, image=img) for img in uploaded_images]
                for img_obj in image_objects:
                    img_obj.save()

        return event
