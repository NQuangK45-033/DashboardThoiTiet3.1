import requests
import sqlite3
from datetime import datetime

API_KEY = "c34651fc396a4dbca9c74656251207"  # API key từ weatherapi.com
DEFAULT_CITY = "Ho Chi Minh"

def fetch_and_save_weather(city=DEFAULT_CITY):
    url = f"http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={city}&lang=vi"
    try:
        res = requests.get(url)
        data = res.json()

        if "error" in data:
            print("❌ Lỗi API:", data["error"]["message"])
            return False

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        temp = data['current']['temp_c']
        humidity = data['current']['humidity']
        wind = round(data['current']['wind_kph'] / 3.6, 2)
        status = data['current']['condition']['text']

        conn = sqlite3.connect("weather.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO weather_data (city, datetime, temp, humidity, wind, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (city, now, temp, humidity, wind, status))
        conn.commit()
        conn.close()

        print(f"✅ Đã lưu: {city}, {now}, {temp}°C, {humidity}%, {wind} m/s, {status}")
        return True

    except Exception as e:
        print("❌ Lỗi hệ thống:", e)
        return False

if __name__ == "__main__":
    fetch_and_save_weather()
