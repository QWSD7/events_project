from django.contrib import admin
from django.utils.html import format_html
from .models import Location, Event, EventImage, WeatherData, EmailSettings


# Inline для изображений (позволим админу загружать несколько фото внутри Event)
class EventImageInline(admin.TabularInline):
    model = EventImage
    extra = 1
    readonly_fields = ['image_preview']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 100px;"/>', obj.image.url)
        return 'нет изображения'
    image_preview.short_description = "Предпросмотр"

# Inline для погоды (просмотр в карточке локации)
class WeatherDataInline(admin.StackedInline):
    model = WeatherData
    readonly_fields = [
        'temperature', 'humidity', 'pressure',
        'wind_direction', 'wind_speed', 'updated_at'
    ]
    can_delete = False
    verbose_name = "Актуальная погода"

    #запрещаем добавлять новые записи вручную через админку
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'latitude', 'longitude', 'get_temp']
    search_fields = ['name']
    inlines = [WeatherDataInline]

    def get_temp(self, obj):
        if hasattr(obj, 'weather'):
            return f"{obj.weather.order_by('-updated_at').first()}°C"
        return '-'
    get_temp.short_description = "Температура"

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    # Поля в списке
    list_display = ['title', 'status', 'location', 'start_date', 'rating', 'get_thumbnail']

    # Боковые фильтры
    list_filter = ['status', 'location', 'start_date', 'rating']

    # Поиск по названию мероприятия или названию места (согласно тех. заданию)
    search_fields = ['title', 'location__name']

    # Позволяет менять статус прямо в списке
    list_editable = ['status']

    # Группировка полей в форме редактирования
    fieldsets = (
        ("Основная информация", {
            'fields': ('title', 'description', 'author', 'status')
        }),
        ("Место и Время", {
            'fields': ('location', 'pub_date', 'start_date', 'end_date')
        }),
        ("Дополнительно", {
            'fields': ('rating', 'thumbnail')
        }),
    )

    # Поле thumbnail только для чтения, так как оно заполняется автоматически
    readonly_fields = ['thumbnail', 'get_thumbnail_large']
    inlines = [EventImageInline]

    def get_thumbnail(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="max-height: 50px;" />', obj.thumbnail.url)
        return "Нет превью"
    get_thumbnail.short_description = "Превью"

    def get_thumbnail_large(self, obj):
        if obj.thumbnail:
            return format_html('<img src="{}" style="max-height: 200px;" />', obj.thumbnail.url)
        return "Превью еще не создано"

    get_thumbnail_large.short_description = "Размер превью (200px)"


@admin.register(WeatherData)
class WeatherDataAdmin(admin.ModelAdmin):
    # Отдельный раздел для погоды (только для чтения согласно тех. заданию)
    list_display = ['location', 'temperature', 'humidity', 'updated_at']

    def has_add_permission(self, request): return False

    def has_change_permission(self, request, obj=None): return False


@admin.register(EmailSettings)
class EmailSettingsAdmin(admin.ModelAdmin):
    # Поля, которые будут отображаться в списке (хотя запись будет одна)
    list_display = ('__str__', 'subject_template')

    # Группируем поля для удобства
    fieldsets = (
        ("Шаблон письма", {
            'fields': ('subject_template', 'message_template'),
            'description': "Доступные переменные: {title}, {location}, {start_date}, {weather}"
        }),
        ("Получатели", {
            'fields': ('recipients_text',),
        }),
    )

    def has_add_permission(self, request):
        # Если запись уже есть, кнопку "Добавить" убираем
        if self.model.objects.exists():
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        # Запрещаем удалять настройки, чтобы таск не упал
        return False

    # Опционально: делаем так, чтобы нельзя было выбрать несколько записей в списке
    actions = None
