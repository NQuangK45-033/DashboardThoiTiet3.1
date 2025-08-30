from flask import Flask, render_template, request, redirect, url_for, Response
import csv, io
import sqlite3
import requests
from datetime import datetime

app = Flask(__name__)
API_KEY = "c34651fc396a4dbca9c74656251207"
BASE_URL = "http://api.weatherapi.com/v1/current.json"

def translate_status(status):
    translations = {
        "Sunny": "Trời nắng", "Clear": "Trời quang đãng", "Partly cloudy": "Trời ít mây",
        "Cloudy": "Nhiều mây", "Overcast": "U ám", "Mist": "Sương mù nhẹ",
        "Patchy light rain with thunder": "Mưa nhẹ từng cơn kèm sấm sét",
        "Torrential rain shower": "Mưa rào xối xả", "Light rain": "Mưa nhẹ",
        "Moderate or heavy rain with thunder": "Mưa vừa hoặc nặng hạt có sấm sét"
    }
    return translations.get(status.strip(), status)

def get_grouping_sql(group_by):
    if group_by == "hour":
        return "strftime('%H', datetime)"
    elif group_by == "dow":
        return "strftime('%w', datetime)"
    elif group_by == "day":
        return "strftime('%Y-%m-%d', datetime)"
    elif group_by == "week":
        return "strftime('%Y-W%W', datetime)"
    elif group_by == "month":
        return "strftime('%Y-%m', datetime)"
    elif group_by == "quarter":
        return """strftime('%Y', datetime) || '-Q' ||
                CASE
                    WHEN CAST(strftime('%m', datetime) AS INT) BETWEEN 1 AND 3 THEN '1'
                    WHEN CAST(strftime('%m', datetime) AS INT) BETWEEN 4 AND 6 THEN '2'
                    WHEN CAST(strftime('%m', datetime) AS INT) BETWEEN 7 AND 9 THEN '3'
                    ELSE '4'
                END"""
    else:
        return "strftime('%Y-%m-%d', datetime)"


def get_favorites():
    conn = sqlite3.connect("weather.db")
    cur = conn.cursor()
    cur.execute("SELECT city FROM favorite_cities ORDER BY city")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


@app.route("/favorites/add", methods=["POST"])
def add_favorite():
    city = request.form.get("city", "").strip()
    if city:
        conn = sqlite3.connect("weather.db")
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO favorite_cities(city) VALUES(?)", (city,))
        conn.commit()
        conn.close()
    return redirect(url_for("main"))

@app.route("/favorites/remove", methods=["POST"])
def remove_favorite():
    city = request.form.get("city", "").strip()
    if city:
        conn = sqlite3.connect("weather.db")
        cur = conn.cursor()
        cur.execute("DELETE FROM favorite_cities WHERE city=?", (city,))
        conn.commit()
        conn.close()
    return redirect(url_for("main"))


def rolling_mean(series, window):
    # series có thể chứa None (do ghép nhãn), ta bỏ qua None trong cửa sổ
    out = []
    buf = []
    from collections import deque
    dq = deque(maxlen=window)
    for v in series:
        dq.append(v)
        vals = [x for x in dq if x is not None]
        out.append(round(sum(vals)/len(vals), 2) if vals else None)
    return out

def pick_window(group):
    return {
        "hour": 3,      # 3 giờ
        "day": 7,       # 7 ngày
        "week": 4,      # 4 tuần
        "month": 3,     # 3 tháng
        "quarter": 2,   # 2 quý
        "dow": 3
    }.get(group, 3)


@app.route("/export_csv")
def export_csv():
    # Lấy params giống dashboard
    selected_cities = request.args.getlist("cities")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    conn = sqlite3.connect("weather.db")
    cur = conn.cursor()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["city", "datetime", "temp_C", "humidity_%", "wind_mps", "status"])

    if selected_cities:
        placeholders = ",".join("?" for _ in selected_cities)
        q = f"SELECT city, datetime, temp, humidity, wind, status FROM weather_data WHERE city IN ({placeholders})"
        params = list(selected_cities)
        if start_date and end_date:
            q += " AND date(datetime) BETWEEN ? AND ?"
            params += [start_date, end_date]
        q += " ORDER BY datetime DESC"
        for row in cur.execute(q, tuple(params)):
            writer.writerow(row)

    conn.close()
    csv_data = output.getvalue()
    output.close()
    fname = "weather_export.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"}
    )



@app.route("/", methods=["GET", "POST"])
def main():
    # === Lấy đầu vào ===
    favorites = get_favorites()
    group = request.args.get("group", "day")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # 1) POST: người dùng bấm "Lấy dữ liệu" cho 1 city -> gọi API và lưu giống cũ
    if request.method == "POST":
        city_post = request.form.get("city", "Ho Chi Minh")
        url = f"{BASE_URL}?key={API_KEY}&q={city_post}"   # bạn đang dùng weatherapi.com:contentReference[oaicite:1]{index=1}
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            if "error" not in data:
                current = data["current"]
                weather = {
                    "city": city_post,
                    "temp": current["temp_c"],
                    "humidity": current["humidity"],
                    "wind": round(current["wind_kph"] / 3.6, 2),
                    "status": current["condition"]["text"],
                    "status_vi": translate_status(current["condition"]["text"]),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                conn = sqlite3.connect("weather.db")
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR IGNORE INTO weather_data(city, datetime, temp, humidity, wind, status)
                    VALUES(?,?,?,?,?,?)
                """, (weather["city"], weather["time"], weather["temp"],
                      weather["humidity"], weather["wind"], weather["status"]))
                conn.commit()
                conn.close()

    # 2) GET: xem dashboard so sánh nhiều city
    #    nhận nhiều giá trị ?cities=Hanoi&cities=Da%20Nang...
    selected_cities = request.args.getlist("cities")
    if not selected_cities:
        # Mặc định: nếu có favorites thì chọn 1–2 city đầu, không thì Ho Chi Minh
        selected_cities = favorites[:2] if favorites else ["Ho Chi Minh"]

    group_sql = get_grouping_sql(group)  # tái dùng hàm nhóm có sẵn:contentReference[oaicite:2]{index=2}
    datasets = []
    common_labels = None  # hợp nhất mốc thời gian

    conn = sqlite3.connect("weather.db")
    cur = conn.cursor()

    for city in selected_cities:
        query = f"""
            SELECT {group_sql} AS label, AVG(temp), AVG(humidity), AVG(wind)
            FROM weather_data
            WHERE city=?
        """
        params = [city]
        if start_date and end_date:
            query += " AND date(datetime) BETWEEN ? AND ?"
            params += [start_date, end_date]
        query += " GROUP BY label ORDER BY label ASC"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        labels = [r[0] for r in rows]
        temps = [round(r[1] or 0, 2) for r in rows]
        humidities = [round(r[2] or 0, 2) for r in rows]
        winds = [round(r[3] or 0, 2) for r in rows]

        datasets.append({
            "city": city,
            "labels": labels,
            "temps": temps,
            "humidities": humidities,
            "winds": winds
        })

        # gom tất cả nhãn thời gian
        if common_labels is None:
            common_labels = list(labels)
        else:
            common_labels = sorted(set(common_labels).union(labels))

    conn.close()

    # Chuẩn hoá độ dài (padding None) để Chart.js vẽ thẳng hàng theo common_labels
    def align(series_labels, series_values, all_labels):
        m = {lbl: val for lbl, val in zip(series_labels, series_values)}
        return [m.get(lbl, None) for lbl in all_labels]

    for d in datasets:
        d["temps"] = align(d["labels"], d["temps"], common_labels)
        d["humidities"] = align(d["labels"], d["humidities"], common_labels)
        d["winds"] = align(d["labels"], d["winds"], common_labels)

    # Thống kê tổng quát cho city đầu (tuỳ chọn)
    first_temps = [v for v in (datasets[0]["temps"] if datasets else []) if v is not None]
    avg_temp = round(sum(first_temps) / len(first_temps), 2) if first_temps else 0
    max_temp = max(first_temps) if first_temps else 0
    min_temp = min(first_temps) if first_temps else 0


    # === Thêm SMA cho biểu đồ phụ ===
    sma_window = pick_window(group)
    for d in datasets:
        d["temps_sma"] = rolling_mean(d["temps"], sma_window)
        d["humidities_sma"] = rolling_mean(d["humidities"], sma_window)
        d["winds_sma"] = rolling_mean(d["winds"], sma_window)

    # === Bảng dữ liệu chi tiết (giới hạn 500 dòng gần nhất) ===
    conn = sqlite3.connect("weather.db")
    cur = conn.cursor()
    table_rows = []
    if selected_cities:
        placeholders = ",".join("?" for _ in selected_cities)
        query_tbl = f"""
          SELECT city, datetime, temp, humidity, wind, status
          FROM weather_data
          WHERE city IN ({placeholders})
        """
        params_tbl = list(selected_cities)
        if start_date and end_date:
            query_tbl += " AND date(datetime) BETWEEN ? AND ?"
            params_tbl += [start_date, end_date]
        query_tbl += " ORDER BY datetime DESC LIMIT 500"
        cur.execute(query_tbl, tuple(params_tbl))
        table_rows = cur.fetchall()
    conn.close()




    return render_template(
        "main.html",
        favorites=favorites,
        selected_cities=selected_cities,
        labels=common_labels or [],
        datasets=datasets,
        group=group,
        start_date=start_date,
        end_date=end_date,
        avg_temp=avg_temp, max_temp=max_temp, min_temp=min_temp,
        sma_window=sma_window,
        table_rows=table_rows
    )

if __name__ == "__main__":
    app.run(debug=True)
