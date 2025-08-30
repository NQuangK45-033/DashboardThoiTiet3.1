import sqlite3

# Kết nối đến file weather.db
conn = sqlite3.connect("weather.db")
cursor = conn.cursor()

# Truy vấn dữ liệu
cursor.execute("SELECT * FROM weather_data ORDER BY datetime DESC LIMIT 100")
rows = cursor.fetchall()

# In kết quả ra màn hình
for row in rows:
    print(row)

conn.close()
