import os

from celery import Celery

# Устанавливаем настройки Djnago по умолчанию для Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")

app.config_from_object("django.conf:settings", namespace="CELERY")

# поиск задач (task.py) в приложениях django
app.autodiscover_tasks()
