import logging
import requests
from environ import Env

env = Env()

logger = logging.getLogger(__name__)

def get_weather_for_coordinates(lat, lon):
    """
    Получаем данные о погоде через OpenWeather API.
    """
    api_key = env("OPENWEATHER_API")
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=ru"

    try:
        logger.info(f"Запуск получения информации о погоде")
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            result = {
                "temperature": data["main"]["temp"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "wind_speed": data["wind"]["speed"],
                "wind_direction": str(data["wind"]["deg"]),
                "description": data["weather"][0]["description"],
            }

            logger.info(f"Данные о погоде успешно получены: {result['temperature']}°C, {result['description']}")
            return result
    except Exception as e:
        logger.error(f"Ошибка при получении погоды: {e}")
    return None
