from rest_framework import  serializers
from .models import Event, Location, EventImage, WeatherData

class LocationSerializer(serializers.ModelSerializer):
    temperature = serializers.FloatField(source='weather.temperature', read_only=True)
    humidity = serializers.IntegerField(source='weather.humidity', read_only=True)
    pressure = serializers.FloatField(source='weather.pressure', read_only=True)
    wind_direction = serializers.CharField(source='weather.wind_direction', read_only=True)
    wind_speed = serializers.FloatField(source='weather.wind_speed', read_only=True)
    updated_at = serializers.DateTimeField(source='weather.updated_at', read_only=True)

    class Meta:
        model = Location
        fields = ['id', 'name', 'latitude', 'longitude', 'temperature',
                  'humidity', 'pressure', 'wind_direction', 'wind_speed', 'updated_at']

class EventImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventImage
        fields = ['id', 'image']

class EventSerializer(serializers.ModelSerializer):
    # Вложенный сериализатор для места проведения (только чтение)
    location_details = LocationSerializer(source='location', read_only=True)

    # Список всех изображений мероприятия
    images = EventImageSerializer(many=True, read_only=True)

    # Позволяем загружать файлы при создании
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only = True,
        required=False
    )

    class Meta:
        model = Event
        fields = [
            'id', 'title', 'description', 'author', 'location', 'location_details', 'images', 'uploaded_images',
            'thumbnail', 'pub_date', 'start_date', 'end_date', 'rating', 'status'
        ]
        read_only_fields = ['author', 'preview_image', 'pub_date']

    def validate_rating(self, value):
        """
        Проверка рейтинга по тех. заданию (от 0 до 25)
        """
        if not (0 <= value <= 25):
            raise serializers.ValidationError("Рейтинг должен быть в диапазоне от 0 до 25.")
        return value

    def create(self, validated_data):
        # Извлекаем изображение из валидных данных
        uploaded_images = validated_data.pop('uploaded_images', [])

        #Создаём основное мероприятие
        event = Event.objects.create(**validated_data)

        # Создаём объекты EventImage для каждой картинки
        for image in uploaded_images:
            EventImage.objects.create(event=event, image=image)
        return event