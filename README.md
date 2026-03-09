# Event Managment Service (DRF + Celery)
Современный сервис для управления мероприятиями с автоматическим отслеживанием погоды, системой уведомлений и инструментами для работы с данными в формате Excel.

## Основные возможности:
- Управление мероприятиями: Полный CRUD с поддержкой загрузки нескольких изображения и автоматической генерации превью (200px).
- Гео-локации и Погода: Интеграция с  OpenWeather API для автоматического обновления данных о погоде в местах проведения каждые 60 минут.
- Умные Сelery задачи: Автоматическая публикация отложенных мероприятий.
	- Email-рассылка при публикации (шаблон настраивается через админ. панель)
- Обработка данных: Импорт и экспорт данных в формате `.xlsx` (Excel) с сохранением всех фильтров.
- API Документация: Полная интерактивная документация Swagger. 

## Технологический стек:
- Backernd: Python 3.11, Django 5.x, Django REST Framework
- Database: PostgreSQL 15.
- Task Queue: Celery + Redis.
- Tools: Pillow (обработка фото), openpyxl(Excel), drf-spectacular (Swagger)
- DevOps: Docker & Docker compose

---
## Быстрый запуск (Docker)

1. Клонирование репозитория:
```shell
git clone https://github.com/QWSD7/events_project.git
cd events_project
```

2. Настройка окружения:
```env
# Основные настройки Django
DEBUG=1
SECRET_KEY=your_django_secret_key
ALLOWED_HOSTS=localhost,127.0.0.1

# Настройки PostgreSQL (для Docker-контейнера db)
POSTGRES_DB=events_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

# Строка подключения к БД (используется в settings.py)
DATABASE_URL=postgres://postgres:postgres@db:5432/events_db

# Очереди задач (Celery + Redis)
CELERY_BROKER_URL=redis://redis:6379/0

# Внешние API (согласно ТЗ по погоде)
OPENWEATHER_API=your_openweather_api_key_here

# Настройки почты (согласно ТЗ по уведомлениям)
EMAIL_HOST=smtp.mail.ru
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=example@mail.ru
EMAIL_HOST_PASSWORD=your_app_specific_password
```

3. Запуск проекта:
```shell
docker-compose up --build
```

Приложение будет доступно по адресу: `http://localhost:8000`

---
# Документация API

После запуска проекта документация в следующих форматах:
- Swagger UI: http://localhost:8000/api/docs

---
# Административный интерфейс

Для управления настройками рассылки и модерации
1. Создайте суперпользователя (в другой командной строке в том же пути проекта, после запуска проекта): 
```shell
docker-compose exec django python manage.py createsuperuser
``` 
2. Перейдите по пути http://localhost:8000/admin и авторизуйтесь
3. В разделе "Настройки уведомлений" нужно создать запись настроек, во время создания записи будут предложены стандартные шаблоны темы, текста письма и почты. Доступно редактирование стандартного шаблона.

---
## Тестирование 

Для запуска тестов и генерации отчета о покрытии выполните команды:

Запуск тестов:

```shell
docker-compose exec django coverage run manage.py test events
```

Просмотр отчета в консоли:
```shell
docker-compose exec django coverage report
```

Генерация HTML-отчета (подробно):
```shell
docker-compose exec django coverage html
```

После выполнения отчет будет доступен в папке `htmlcov/index.html`.

