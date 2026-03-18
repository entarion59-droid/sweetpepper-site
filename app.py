#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import json
import os
from datetime import datetime, timedelta
from functools import wraps
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sweetpepper_secret_2025")

MENU_FILE = "menu.json"
CAFE_INFO_FILE = "cafe_info.json"
EVENTS_FILE = "events.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "pepper2025")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

# Cloudinary config — берём из переменных окружения
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", "dqxc3rfml"),
    api_key=os.environ.get("CLOUDINARY_API_KEY", "735795974666715"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "CvGvLny8_D8HPdGTv2C1oZO28sU")
)

# ─────────────────────────────────────────────
#  ЗАЩИТА ОТ БРУТФОРСА
# ─────────────────────────────────────────────

# Хранит: {ip: {"attempts": N, "blocked_until": datetime}}
login_attempts = {}
MAX_ATTEMPTS = 5        # максимум попыток
BLOCK_MINUTES = 15      # блокировка на 15 минут

def get_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)

def is_blocked(ip):
    if ip not in login_attempts:
        return False
    data = login_attempts[ip]
    if data.get("blocked_until") and datetime.now() < data["blocked_until"]:
        return True
    if data.get("blocked_until") and datetime.now() >= data["blocked_until"]:
        # Разблокируем
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

# ─────────────────────────────────────────────
#  HELPERS
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

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def load_menu():
    if os.path.exists(MENU_FILE):
        try:
            with open(MENU_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    return data
        except Exception:
            pass
    return FALLBACK_MENU

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
    if os.path.exists(CAFE_INFO_FILE):
        try:
            with open(CAFE_INFO_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception:
            pass
    return defaults

def save_cafe_info(info):
    with open(CAFE_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

def load_events():
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_events(events):
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
#  PUBLIC ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    menu = load_menu()
    info = load_cafe_info()
    events = load_events()
    return render_template("index.html", menu=menu, info=info, events=events)

@app.route("/lunch")
def lunch():
    info = load_cafe_info()
    return render_template("lunch.html", info=info)

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
#  ADMIN ROUTES
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
                error = f"Аккаунт заблокирован на {BLOCK_MINUTES} минут."
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
    return render_template("admin.html", menu=menu, info=info, events=events)

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
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(menu, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})

# ─────────────────────────────────────────────
#  ЗАГРУЗКА ФОТО (Cloudinary)
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
        return jsonify({"ok": False, "error": "Недопустимый формат. Используй JPG, PNG, WEBP"}), 400
    try:
        result = cloudinary.uploader.upload(
            file,
            folder="sweetpepper",
            transformation=[{"quality": "auto", "fetch_format": "auto"}]
        )
        url = result["secure_url"]
        return jsonify({"ok": True, "url": url})
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
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(menu, f, ensure_ascii=False, indent=2)
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
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(menu, f, ensure_ascii=False, indent=2)
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
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            json.dump(menu, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
