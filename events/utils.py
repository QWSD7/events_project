import requests
from environ import Env

env = Env()

def get_weather_for_coordinates(lat, lon):
    """
    Получаем данные о погоде через OpenWeather API.
    """
    api_key = env('OPENWEATHER_API')
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=ru"

    try:
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            return {
                'temperature': data['main']['temp'],
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'wind_speed': data['wind']['speed'],
                'wind_direction': str(data['wind']['deg']),
                "description": data["weather"][0]["description"]
            }
    except Exception as e:
        print(f"Ошибка при получении погоды: {e}")
    return None