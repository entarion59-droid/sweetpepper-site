#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_from_directory
import json
import os
import base64
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "sweetpepper_secret_2025"

MENU_FILE = "menu.json"
CAFE_INFO_FILE = "cafe_info.json"
EVENTS_FILE = "events.json"
ADMIN_PASSWORD = "pepper2025"

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def load_menu():
    if os.path.exists(MENU_FILE):
        try:
            with open(MENU_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

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
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        error = "Неверный пароль"
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
