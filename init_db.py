import sqlite3

conn = sqlite3.connect("weather.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS weather_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT,
    datetime TEXT,
    temp REAL,
    humidity INTEGER,
    wind REAL,
    status TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS favorite_cities(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  city TEXT UNIQUE
)
""")
# --- DỌN TRÙNG: giữ lại bản ghi có rowid nhỏ nhất cho mỗi (city, datetime)
cursor.execute("""
DELETE FROM weather_data
WHERE rowid NOT IN (
  SELECT MIN(rowid) FROM weather_data
  GROUP BY city, datetime
)
""")

# Chống trùng dữ liệu theo city + thời điểm (khuyến nghị)
cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_weather_unique ON weather_data(city, datetime)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_weather_city_time ON weather_data(city, datetime)")

conn.commit()
conn.close()
print("✅ Đã tạo thành công database 'weather.db' và bảng 'weather_data'.")
