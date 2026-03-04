from django.contrib import admin
from .models import Location, Event, EventImage, WeatherData

admin.site.register(Location)
admin.site.register(Event)
admin.site.register(EventImage)
admin.site.register(WeatherData)
