import schedule
import time
import requests
import sqlite3
import os
from datetime import datetime

API_KEY = "c34651fc396a4dbca9c74656251207"
BASE_URL = "http://api.weatherapi.com/v1/current.json"
CITIES = ["Ho Chi Minh", "Hanoi", "Da Nang", "Can Tho"]

# ❗ Đường dẫn đến file database
DB_PATH = r"D:\Users\ADMIN\Documents\2025_ThS.N1\Phantichdulieu\WeatherDashboard2.0\weather.db"

# ✅ Đường dẫn file log (cùng thư mục với script)
LOG_FILE = os.path.join(os.path.dirname(__file__), "log.txt")

def write_log(message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")

def fetch_weather(city):
    try:
        url = f"{BASE_URL}?key={API_KEY}&q={city}&lang=vi"
        res = requests.get(url, timeout=10)
        data = res.json()

        if "error" in data:
            error_msg = f"❌ Lỗi từ API cho {city}: {data['error']['message']}"
            print(error_msg)
            write_log(error_msg)
            return

        current = data["current"]
        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO weather_data (city, datetime, temp, humidity, wind, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            city,
            dt,
            current["temp_c"],
            current["humidity"],
            round(current["wind_kph"] / 3.6, 2),
            current["condition"]["text"]
        ))
        conn.commit()
        conn.close()

        success_msg = f"✅ Đã lưu dữ liệu cho {city} lúc {dt}"
        print(success_msg)
        write_log(success_msg)

    except Exception as e:
        err_msg = f"⚠️ Lỗi khi lấy dữ liệu cho {city}: {e}"
        print(err_msg)
        write_log(err_msg)

def job():
    start_msg = f"\n🔁 Bắt đầu thu thập lúc {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    print(start_msg)
    write_log(start_msg)
    for city in CITIES:
        fetch_weather(city)

# Lên lịch chạy thử mỗi 1 phút (có thể đổi lại thành mỗi ngày lúc 07:00 nếu cần)
# schedule.every().day.at("07:00").do(job)
schedule.every(1).minutes.do(job)

print("🕒 Đang chạy auto_fetch.py – chờ đến 07:00 hoặc chạy thử mỗi 1 phút...")
write_log("🟢 Khởi động script auto_fetch.py")

while True:
    schedule.run_pending()
    time.sleep(60)
