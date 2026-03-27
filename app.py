#!/usr/bin/env python3

from flask import Flask, render_template, jsonify, request, session, redirect, url_for, Response
import json
import os
from datetime import datetime, timedelta
from functools import wraps
import cloudinary
import cloudinary.uploader
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

DATABASE_URL = os.environ.get("DATABASE_URL")

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET")
)

# ─────────────────────────────────────────────
# DATABASE POOL
# ─────────────────────────────────────────────

db_pool = pool.ThreadedConnectionPool(1, 10, DATABASE_URL)

def get_db():
    conn = db_pool.getconn()
    conn.cursor_factory = RealDictCursor
    return conn

def release_db(conn):
    db_pool.putconn(conn)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cur.execute("SELECT key FROM settings WHERE key = 'menu'")
    if not cur.fetchone():
        menu_data = {}
        if os.path.exists("menu.json"):
            try:
                with open("menu.json", "r", encoding="utf-8") as f:
                    menu_data = json.load(f)
            except:
                pass
        if not menu_data:
            menu_data = FALLBACK_MENU
        cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s)",
                    ("menu", json.dumps(menu_data, ensure_ascii=False)))

    cur.execute("SELECT key FROM settings WHERE key = 'lunch'")
    if not cur.fetchone():
        lunch_data = {}
        if os.path.exists("lunch.json"):
            try:
                with open("lunch.json", "r", encoding="utf-8") as f:
                    lunch_data = json.load(f)
            except:
                pass
        cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s)",
                    ("lunch", json.dumps(lunch_data, ensure_ascii=False)))

    cur.execute("SELECT key FROM settings WHERE key = 'events'")
    if not cur.fetchone():
        events_data = []
        if os.path.exists("events.json"):
            try:
                with open("events.json", "r", encoding="utf-8") as f:
                    events_data = json.load(f)
            except:
                pass
        cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s)",
                    ("events", json.dumps(events_data, ensure_ascii=False)))

    cur.execute("SELECT key FROM settings WHERE key = 'cafe_info'")
    if not cur.fetchone():
        info_data = {}
        if os.path.exists("cafe_info.json"):
            try:
                with open("cafe_info.json", "r", encoding="utf-8") as f:
                    info_data = json.load(f)
            except:
                pass
        cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s)",
                    ("cafe_info", json.dumps(info_data, ensure_ascii=False)))

    cur.execute("""
        CREATE TABLE IF NOT EXISTS page_views (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL DEFAULT CURRENT_DATE,
            count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(date)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dish_views (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            dish_name TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(category, dish_name)
        )
    """)

    conn.commit()
    cur.close()
    release_db(conn)

def db_get(key):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    release_db(conn)
    return json.loads(row["value"]) if row else None

def db_set(key, value):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO settings (key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, (key, json.dumps(value, ensure_ascii=False)))
    conn.commit()
    cur.close()
    release_db(conn)

# ─────────────────────────────────────────────
# FALLBACK MENU
# ─────────────────────────────────────────────

FALLBACK_MENU = {
    "🍳 Завтраки": [{"name": "Овсянка с топпингом", "description": "280 г", "price": 205, "weight": "280 г", "kbju": "", "photo": ""}],
    "🥗 Закуски и салаты": [{"name": "Камамбер фри", "description": "130 г, с ягодным соусом", "price": 335, "weight": "130 г", "kbju": "", "photo": ""}],
    "🍲 Супы и горячее": [{"name": "Фирменный борщ", "description": "350 г, с говядиной", "price": 260, "weight": "350 г", "kbju": "", "photo": ""}],
    "🍝 Пасты": [{"name": "Спагетти Карбонара", "description": "250 г, с беконом", "price": 365, "weight": "250 г", "kbju": "", "photo": ""}],
    "🥐 Бейглы и сэндвичи": [{"name": "Цезарь-бейгл", "description": "240 г, с цыплёнком", "price": 325, "weight": "240 г", "kbju": "", "photo": ""}],
    "🍰 Десерты": [{"name": "Чизкейк Сан Себастьян", "description": "", "price": 335, "weight": "", "kbju": "", "photo": ""}],
    "☕ Кофе и чай": [{"name": "Капучино", "description": "150 мл", "price": 175, "weight": "150 мл", "kbju": "", "photo": ""}],
    "🍹 Безалкогольные напитки": [{"name": "Лимонад домашний", "description": "300 мл", "price": 185, "weight": "300 мл", "kbju": "", "photo": ""}],
    "🍸 Коктейли авторские": [{"name": "Эйприл", "description": "250 мл", "price": 355, "weight": "250 мл", "kbju": "", "photo": ""}],
    "🍹 Коктейли классика": [{"name": "Пина Колада", "description": "300 мл, ром, ананас", "price": 425, "weight": "300 мл", "kbju": "", "photo": ""}],
    "🥃 Виски": [{"name": "Jack Daniels", "description": "40 мл, американский", "price": 365, "weight": "40 мл", "kbju": "", "photo": ""}],
    "🍷 Вино": [{"name": "Tarapaca Merlo", "description": "125 мл / 750 мл, Чили", "price": 315, "weight": "125 мл", "kbju": "", "photo": ""}],
    "🍺 Пиво": [{"name": "Крушовице", "description": "450 мл, 4.8%", "price": 225, "weight": "450 мл", "kbju": "", "photo": ""}],
    "🌶 Настойки Sweet Pepper": [{"name": "Солёная Карамель", "description": "40 мл / 500 мл", "price": 150, "weight": "40 мл", "kbju": "", "photo": ""}],
}

# ─────────────────────────────────────────────
# АНАЛИТИКА
# ─────────────────────────────────────────────

BOT_AGENTS = ["bot", "spider", "crawler", "slurp", "baiduspider", "yandex", "googlebot",
              "bingbot", "duckduckbot", "facebookexternalhit", "curl", "wget", "python-requests"]

def is_bot():
    ua = request.headers.get("User-Agent", "").lower()
    return any(b in ua for b in BOT_AGENTS)

def track_page_view():
    if is_bot():
        return
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO page_views (date, count) VALUES (CURRENT_DATE, 1)
            ON CONFLICT (date) DO UPDATE SET count = page_views.count + 1
        """)
        conn.commit()
        cur.close()
        release_db(conn)
    except Exception:
        pass

def track_dish_view(category, dish_name):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO dish_views (category, dish_name, count) VALUES (%s, %s, 1)
            ON CONFLICT (category, dish_name) DO UPDATE SET count = dish_views.count + 1
        """, (category, dish_name))
        conn.commit()
        cur.close()
        release_db(conn)
    except Exception:
        pass

def get_analytics():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT date::text, count FROM page_views
            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY date
        """)
        views_by_day = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT category, dish_name, count FROM dish_views
            ORDER BY count DESC LIMIT 10
        """)
        top_dishes = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT count FROM page_views WHERE date = CURRENT_DATE")
        row = cur.fetchone()
        today = row["count"] if row else 0

        cur.execute("SELECT SUM(count) FROM page_views WHERE date >= CURRENT_DATE - INTERVAL '7 days'")
        row = cur.fetchone()
        week = row["sum"] if row and row["sum"] else 0

        cur.execute("SELECT SUM(count) FROM page_views WHERE date >= CURRENT_DATE - INTERVAL '30 days'")
        row = cur.fetchone()
        month = row["sum"] if row and row["sum"] else 0

        cur.close()
        release_db(conn)
        return {
            "views_by_day": views_by_day,
            "top_dishes": top_dishes,
            "today": today,
            "week": week,
            "month": month
        }
    except Exception as e:
        return {"views_by_day": [], "top_dishes": [], "today": 0, "week": 0, "month": 0}

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def load_menu():
    data = db_get("menu")
    return data if data else FALLBACK_MENU

def save_menu(menu):
    db_set("menu", menu)

def load_cafe_info():
    defaults = {
        "name": "Sweet Pepper",
        "address": "г. Ярославль, ул. Кирова, 10-25",
        "hours": "Пн-Сб: 8:30–2:00 | Вс: 10:30–2:00",
        "phone": "",
        "promo": "🎉 Закажи 3 настойки — получи 4-ю в подарок!",
        "instagram": "",
        "vk": "",
        "telegram": "https://t.me/SweetPepper1025bot",
    }
    data = db_get("cafe_info")
    if data:
        defaults.update(data)
    return defaults

def save_cafe_info(info):
    db_set("cafe_info", info)

def load_events():
    data = db_get("events")
    return data if data else []

def save_events(events):
    db_set("events", events)

def load_lunch():
    data = db_get("lunch")
    return data if data else {}

def save_lunch(lunch):
    db_set("lunch", lunch)

# ─────────────────────────────────────────────
# ЗАЩИТА ОТ БРУТФОРСА
# ─────────────────────────────────────────────

login_attempts = {}
MAX_ATTEMPTS = 5
BLOCK_MINUTES = 15

def get_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)

def is_blocked(ip):
    if ip not in login_attempts:
        return False
    data = login_attempts[ip]
    if data.get("blocked_until") and datetime.now() < data["blocked_until"]:
        return True
    if data.get("blocked_until") and datetime.now() >= data["blocked_until"]:
        login_attempts.pop(ip, None)
    return False

def register_failed_attempt(ip):
    if ip not in login_attempts:
        login_attempts[ip] = {"attempts": 0, "blocked_until": None}
    login_attempts[ip]["attempts"] += 1
    if login_attempts[ip]["attempts"] >= MAX_ATTEMPTS:
        login_attempts[ip]["blocked_until"] = datetime.now() + timedelta(minutes=BLOCK_MINUTES)

def reset_attempts(ip):
    login_attempts.pop(ip, None)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
# ИНИЦИАЛИЗАЦИЯ БД ПРИ СТАРТЕ
# ─────────────────────────────────────────────

try:
    init_db()
except Exception as e:
    print(f"DB init error: {e}")

# ─────────────────────────────────────────────
# PUBLIC ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    track_page_view()
    menu = load_menu()
    info = load_cafe_info()
    events = load_events()
    return render_template("index.html", menu=menu, info=info, events=events)

@app.route("/lunch")
def lunch():
    info = load_cafe_info()
    lunch_data = load_lunch()
    return render_template("lunch.html", info=info, lunch=lunch_data)

@app.route("/robots.txt")
def robots():
    return Response(
        "User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: https://www.sweetpepper-bar.ru/sitemap.xml\n",
        mimetype="text/plain"
    )

@app.route("/sitemap.xml")
def sitemap():
    base = "https://www.sweetpepper-bar.ru"
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += f'  <url><loc>{base}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
    xml += f'  <url><loc>{base}/lunch</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>\n'
    xml += '</urlset>'
    return Response(xml, mimetype="application/xml")

@app.route("/api/track_dish", methods=["POST"])
def api_track_dish():
    data = request.get_json()
    track_dish_view(data.get("category", ""), data.get("dish_name", ""))
    return jsonify({"ok": True})

@app.route("/api/menu")
def api_menu():
    return jsonify(load_menu())

@app.route("/api/info")
def api_info():
    return jsonify(load_cafe_info())

@app.route("/api/events")
def api_events():
    return jsonify(load_events())

# ─────────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    ip = get_ip()
    error = None

    if is_blocked(ip):
        error = f"Слишком много попыток. Попробуйте через {BLOCK_MINUTES} минут."
        return render_template("admin_login.html", error=error)

    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            reset_attempts(ip)
            session["admin"] = True
            session.permanent = True
            app.permanent_session_lifetime = timedelta(hours=8)
            return redirect(url_for("admin_panel"))
        else:
            register_failed_attempt(ip)
            attempts_left = MAX_ATTEMPTS - login_attempts.get(ip, {}).get("attempts", 0)
            if attempts_left <= 0:
                error = f"Заблокировано на {BLOCK_MINUTES} минут."
            else:
                error = f"Неверный пароль. Осталось попыток: {attempts_left}"

    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin_panel():
    menu = load_menu()
    info = load_cafe_info()
    events = load_events()
    lunch = load_lunch()
    analytics = get_analytics()
    return render_template("admin.html", menu=menu, info=info, events=events, lunch=lunch, analytics=analytics)

@app.route("/admin/save_info", methods=["POST"])
@admin_required
def admin_save_info():
    info = load_cafe_info()
    for field in ["name", "address", "hours", "phone", "promo", "instagram", "vk", "telegram"]:
        if field in request.form:
            info[field] = request.form[field]
    save_cafe_info(info)
    return jsonify({"ok": True})

@app.route("/admin/add_event", methods=["POST"])
@admin_required
def admin_add_event():
    data = request.get_json()
    events = load_events()
    event = {
        "id": int(datetime.now().timestamp()),
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "photo": data.get("photo", ""),
        "date": data.get("date", ""),
    }
    events.insert(0, event)
    save_events(events)
    return jsonify({"ok": True, "event": event})

@app.route("/admin/delete_event/<int:event_id>", methods=["POST"])
@admin_required
def admin_delete_event(event_id):
    events = load_events()
    events = [e for e in events if e.get("id") != event_id]
    save_events(events)
    return jsonify({"ok": True})

@app.route("/admin/update_dish", methods=["POST"])
@admin_required
def admin_update_dish():
    data = request.get_json()
    menu = load_menu()
    category = data.get("category")
    idx = data.get("idx")
    field = data.get("field")
    value = data.get("value")
    if category in menu and 0 <= idx < len(menu[category]):
        if field == "price":
            try:
                value = int(value)
            except Exception:
                pass
        menu[category][idx][field] = value
        save_menu(menu)
    return jsonify({"ok": True})

@app.route("/admin/add_dish", methods=["POST"])
@admin_required
def admin_add_dish():
    data = request.get_json()
    menu = load_menu()
    category = data.get("category")
    dish = data.get("dish")
    if category in menu and dish:
        menu[category].append(dish)
        save_menu(menu)
    return jsonify({"ok": True})

@app.route("/admin/delete_dish", methods=["POST"])
@admin_required
def admin_delete_dish():
    data = request.get_json()
    menu = load_menu()
    category = data.get("category")
    idx = data.get("idx")
    if category in menu and 0 <= idx < len(menu[category]):
        old_photo = menu[category][idx].get("photo", "")
        if "cloudinary.com" in old_photo:
            try:
                public_id = "sweetpepper/" + old_photo.split("/sweetpepper/")[1].split(".")[0]
                cloudinary.uploader.destroy(public_id)
            except Exception:
                pass
        menu[category].pop(idx)
        save_menu(menu)
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
# ФОТО
# ─────────────────────────────────────────────

@app.route("/admin/upload_photo", methods=["POST"])
@admin_required
def upload_photo():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Файл не передан"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "Файл не выбран"}), 400
    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "Недопустимый формат"}), 400
    try:
        result = cloudinary.uploader.upload(
            file,
            folder="sweetpepper",
            transformation=[{"quality": "auto", "fetch_format": "auto"}]
        )
        return jsonify({"ok": True, "url": result["secure_url"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/admin/delete_photo", methods=["POST"])
@admin_required
def delete_photo():
    data = request.get_json()
    category = data.get("category")
    idx = data.get("idx")
    menu = load_menu()
    if category in menu and 0 <= idx < len(menu[category]):
        old_photo = menu[category][idx].get("photo", "")
        if "cloudinary.com" in old_photo:
            try:
                public_id = "sweetpepper/" + old_photo.split("/sweetpepper/")[1].split(".")[0]
                cloudinary.uploader.destroy(public_id)
            except Exception:
                pass
        menu[category][idx]["photo"] = ""
        save_menu(menu)
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
# ЛАНЧИ
# ─────────────────────────────────────────────

@app.route("/admin/update_lunch_dish", methods=["POST"])
@admin_required
def admin_update_lunch_dish():
    data = request.get_json()
    lunch = load_lunch()
    category = data.get("category")
    idx = data.get("idx")
    field = data.get("field")
    value = data.get("value")
    if category in lunch and 0 <= idx < len(lunch[category]):
        if field == "price":
            try:
                value = int(value)
            except Exception:
                pass
        lunch[category][idx][field] = value
        save_lunch(lunch)
    return jsonify({"ok": True})

@app.route("/admin/upload_lunch_photo", methods=["POST"])
@admin_required
def upload_lunch_photo():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Файл не передан"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "Файл не выбран"}), 400
    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "Недопустимый формат"}), 400
    try:
        result = cloudinary.uploader.upload(
            file,
            folder="sweetpepper/lunch",
            transformation=[{"quality": "auto", "fetch_format": "auto"}]
        )
        return jsonify({"ok": True, "url": result["secure_url"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/admin/add_lunch_dish", methods=["POST"])
@admin_required
def admin_add_lunch_dish():
    data = request.get_json()
    lunch = load_lunch()
    category = data.get("category")
    dish = data.get("dish")
    if category in lunch and dish:
        lunch[category].append(dish)
        save_lunch(lunch)
    return jsonify({"ok": True})

@app.route("/admin/delete_lunch_dish", methods=["POST"])
@admin_required
def admin_delete_lunch_dish():
    data = request.get_json()
    lunch = load_lunch()
    category = data.get("category")
    idx = data.get("idx")
    if category in lunch and 0 <= idx < len(lunch[category]):
        lunch[category].pop(idx)
        save_lunch(lunch)
    return jsonify({"ok": True})

FALLBACK_LUNCH = {
    "Весенние хиты": [
        {"name": "Буррито", "description": "", "price": 265, "weight": "", "kbju": "Б:16.5 · Ж:18.2 · У:28.4 · 339 ккал", "photo": ""},
        {"name": "Ризотто с грибами", "description": "", "price": 285, "weight": "", "kbju": "Б:21.3 · Ж:17.4 · У:41.1 · 405 ккал", "photo": ""},
    ],
    "Салаты": [
        {"name": "Кобб Салат", "description": "С куриной грудкой, беконом и фирменным соусом или с моцареллой, авокадо и брокколи", "price": 285, "weight": "", "kbju": "Б:14.0 · Ж:31.4 · У:2.7 · 353 ккал", "photo": ""},
        {"name": "Классический Цезарь", "description": "С цыплёнком, гренками, салатом айсберг и фирменным соусом", "price": 245, "weight": "", "kbju": "Б:12.9 · Ж:24.9 · У:6.2 · 300 ккал", "photo": ""},
        {"name": "Грузинский салат", "description": "С моцареллой и свежими овощами в сливочно-острой заправке с грецким орехом", "price": 255, "weight": "", "kbju": "Б:5.1 · Ж:31.0 · У:7.0 · 327 ккал", "photo": ""},
    ],
    "Ланч-хиты": [
        {"name": "Кесадилья", "description": "С цыплёнком и сыром или двойной сыр", "price": 265, "weight": "", "kbju": "Б:23.3 · Ж:13.7 · У:3.1 · 229 ккал", "photo": ""},
        {"name": "Фирменная Брокколи", "description": "В сухарях с пармезаном", "price": 190, "weight": "", "kbju": "Б:8.9 · Ж:17.1 · У:20.5 · 272 ккал", "photo": ""},
        {"name": "Цветная капуста с чили и мёдом", "description": "", "price": 180, "weight": "", "kbju": "Б:8.4 · Ж:1.6 · У:49.1 · 244 ккал", "photo": ""},
        {"name": "Паста с курицей", "description": "Фарфалле с грибами в сливочном соусе", "price": 225, "weight": "", "kbju": "Б:21.3 · Ж:17.4 · У:41.1 · 405 ккал", "photo": ""},
        {"name": "Морковные оладьи", "description": "С карри и семечками", "price": 185, "weight": "", "kbju": "Б:4.2 · Ж:8.5 · У:22.3 · 181 ккал", "photo": ""},
    ],
    "На первое": [
        {"name": "Борщ", "description": "Классика жанра с чесночным тостом и салом на гарнир", "price": 225, "weight": "350 г", "kbju": "Б:10.0 · Ж:22.0 · У:18.1 · 311 ккал", "photo": ""},
        {"name": "Тыквенный суп", "description": "Сливочный с цыплёнком или Веджи", "price": 195, "weight": "300 г", "kbju": "Б:14.0 · Ж:46.9 · У:21.3 · 563 ккал", "photo": ""},
        {"name": "Весенний супчик дня", "description": "Чорба, Сырный или Солянка", "price": 235, "weight": "250 г", "kbju": "Чорба: Б:12.4 · Ж:8.6 · У:18.2 · 201 ккал | Сырный: Б:7.8 · Ж:9.2 · У:14.5 · 171 ккал", "photo": ""},
    ],
    "Сендвич-сеты": [
        {"name": "С цыплёнком", "description": "И картошкой фри", "price": 335, "weight": "", "kbju": "Б:7.7 · Ж:56.1 · У:19.1 · 602 ккал", "photo": ""},
        {"name": "С индейкой", "description": "И картофельными дольками", "price": 345, "weight": "", "kbju": "Б:7.9 · Ж:29.9 · У:31.3 · 425 ккал", "photo": ""},
        {"name": "Бейгл с котлетой", "description": "И картошкой по-ярославски", "price": 355, "weight": "", "kbju": "Б:16.2 · Ж:81.7 · У:80.3 · 1121 ккал", "photo": ""},
    ],
    "Десерты": [
        {"name": "Фирменный штрудель", "description": "Яблочный с орехами и грушами", "price": 150, "weight": "", "kbju": "Б:2.1 · Ж:7.6 · У:15.4 · 138 ккал", "photo": ""},
        {"name": "Малиновый Наполеон", "description": "", "price": 85, "weight": "", "kbju": "Б:0.6 · Ж:1.6 · У:5.6 · 39 ккал", "photo": ""},
        {"name": "Ягодный Коржик", "description": "", "price": 70, "weight": "", "kbju": "", "photo": ""},
    ],
}

@app.route("/admin/reload_menu", methods=["POST"])
@admin_required
def admin_reload_menu():
    try:
        # Сначала пробуем файл, если Railway его не найдёт — используем FALLBACK_MENU
        try:
            with open("menu.json", "r", encoding="utf-8") as f:
                new_menu = json.load(f)
        except Exception:
            new_menu = FALLBACK_MENU
        current_menu = load_menu()
        for cat, dishes in new_menu.items():
            if cat in current_menu:
                for dish in dishes:
                    for current_dish in current_menu[cat]:
                        if current_dish["name"] == dish["name"] and current_dish.get("photo"):
                            dish["photo"] = current_dish["photo"]
                            break
        db_set("menu", new_menu)
        return jsonify({"ok": True, "message": "Меню обновлено, фото сохранены!"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/admin/reload_lunch", methods=["POST"])
@admin_required
def admin_reload_lunch():
    try:
        # Сначала пробуем файл, если Railway его не найдёт — используем FALLBACK_LUNCH
        try:
            with open("lunch.json", "r", encoding="utf-8") as f:
                new_lunch = json.load(f)
        except Exception:
            new_lunch = FALLBACK_LUNCH
        current_lunch = load_lunch()
        # Сохраняем фото
        for cat, dishes in new_lunch.items():
            if cat in current_lunch:
                for dish in dishes:
                    for current_dish in current_lunch[cat]:
                        if current_dish["name"] == dish["name"] and current_dish.get("photo"):
                            dish["photo"] = current_dish["photo"]
                            break
        db_set("lunch", new_lunch)
        return jsonify({"ok": True, "message": "Ланч обновлён, фото сохранены!"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
