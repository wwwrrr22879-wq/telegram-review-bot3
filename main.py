import os
import json
from datetime import datetime
from flask import Flask
import telebot
from telebot import types
import threading

# ====== Налаштування ======
TOKEN = os.getenv("BOT_TOKEN", "7974881474:AAHOzEfo2pOxDdznJK-ED9tGikw6Yl7jZDY")
OWNER_ID = int(os.getenv("OWNER_ID", "1470389051"))  # 1470389051
DATA_FILE = "reviews_data.json"
# ==========================

bot = telebot.TeleBot(TOKEN)

# Flask веб-сервер (щоб Repl не засинав)
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот відгуків працює ✅"

# Завантаження бази
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        reviews_db = json.load(f)
else:
    reviews_db = {"admins": {}, "pending": {}}

def save_db():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(reviews_db, f, ensure_ascii=False, indent=2)

def normalize_tag(tag: str) -> str:
    return tag.strip().lower()

def ensure_admin_exists(tag_raw: str):
    key = normalize_tag(tag_raw)
    if key not in reviews_db["admins"]:
        reviews_db["admins"][key] = {"display": tag_raw.strip(), "reviews": []}
        save_db()
    else:
        reviews_db["admins"][key]["display"] = tag_raw.strip()
        save_db()
    return key

def is_owner(uid):
    return str(uid) == str(OWNER_ID)

# ====== /start ======
@bot.message_handler(commands=['start'])
def start_cmd(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⭐ Залишити відгук", "📊 Подивитись рейтинг")
    if is_owner(message.from_user.id):
        kb.add("🛠️ Адмін-меню")
    bot.send_message(message.chat.id,
                     "👋 Привіт! Я бот для відгуків.\n\n"
                     "— Натисни «⭐ Залишити відгук» щоб оцінити адміна.\n"
                     "— Натисни «📊 Подивитись рейтинг» щоб побачити оцінки.",
                     reply_markup=kb)

# ====== Відгуки ======
@bot.message_handler(func=lambda m: m.text == "⭐ Залишити відгук")
def rate_start(message):
    bot.send_message(message.chat.id, "Введи хештег адміністратора (наприклад, #Шерлок):")
    bot.register_next_step_handler(message, rate_admin)

def rate_admin(message):
    tag = message.text.strip()
    key = ensure_admin_exists(tag)
    kb = types.InlineKeyboardMarkup(row_width=5)
    for i in range(1, 6):
        kb.add(types.InlineKeyboardButton("⭐" * i, callback_data=f"rate|{key}|{i}"))
    bot.send_message(message.chat.id, f"Ти вибрав {tag}. Вибери кількість зірок:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("rate|"))
def rate_callback(call):
    _, key, stars = call.data.split("|")
    stars = int(stars)
    user_id = str(call.from_user.id)
    reviews_db["pending"][user_id] = {"key": key, "stars": stars}
    save_db()
    bot.send_message(call.message.chat.id, "Тепер напиши текст відгуку або '-' щоб пропустити:")
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: str(m.from_user.id) in reviews_db.get("pending", {}))
def save_review(message):
    user_id = str(message.from_user.id)
    p = reviews_db["pending"].pop(user_id)
    key, stars = p["key"], p["stars"]
    text = "" if message.text.strip() == "-" else message.text.strip()
    entry = {
        "user": message.from_user.username or f"id{message.from_user.id}",
        "stars": stars,
        "text": text,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    reviews_db["admins"][key]["reviews"].append(entry)
    save_db()
    bot.send_message(message.chat.id, f"✅ Відгук збережено! {'⭐'*stars}")
    
# ====== Перегляд ======
@bot.message_handler(func=lambda m: m.text == "📊 Подивитись рейтинг")
def show_ratings(message):
    if not reviews_db["admins"]:
        bot.send_message(message.chat.id, "Поки що немає відгуків.")
        return
    txt = ""
    for k, info in reviews_db["admins"].items():
        reviews = info["reviews"]
        if not reviews:
            continue
        avg = round(sum(r["stars"] for r in reviews) / len(reviews), 2)
        txt += f"{info['display']} — {'⭐'*int(avg)} ({avg})\n"
    bot.send_message(message.chat.id, txt or "Поки немає відгуків.")

# ====== Адмін-меню ======
@bot.message_handler(func=lambda m: m.text == "🛠️ Адмін-меню")
def admin_menu(message):
    if not is_owner(message.from_user.id):
        bot.send_message(message.chat.id, "⛔ Доступ заборонено.")
        return
    kb = types.InlineKeyboardMarkup()
    for k, info in reviews_db["admins"].items():
        kb.add(types.InlineKeyboardButton(info["display"], callback_data=f"adm|{k}"))
    bot.send_message(message.chat.id, "Оберіть адміна:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm|") or c.data.startswith("delrev|"))
def admin_actions(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "Немає доступу.")
        return
    data = call.data.split("|")
    if data[0] == "adm":
        key = data[1]
        info = reviews_db["admins"].get(key)
        if not info or not info["reviews"]:
            bot.send_message(call.message.chat.id, f"{key} — немає відгуків.")
            return
        kb = types.InlineKeyboardMarkup()
        text = [f"📋 Відгуки для {info['display']}:"]
        for i, r in enumerate(info["reviews"]):
            line = f"{i+1}. {r['user']} — {'⭐'*r['stars']}"
            if r['text']:
                line += f" — {r['text']}"
            text.append(line)
            kb.add(types.InlineKeyboardButton(f"🗑 Видалити #{i+1}", callback_data=f"delrev|{key}|{i}"))
        bot.send_message(call.message.chat.id, "\n".join(text), reply_markup=kb)
    elif data[0] == "delrev":
        _, key, idx = data
        idx = int(idx)
        reviews = reviews_db["admins"].get(key, {}).get("reviews", [])
        if 0 <= idx < len(reviews):
            rem = reviews.pop(idx)
            save_db()
            bot.send_message(call.message.chat.id, f"✅ Видалено: {rem['user']} ({'⭐'*rem['stars']})")
        else:
            bot.send_message(call.message.chat.id, "Відгук не знайдено.")
    bot.answer_callback_query(call.id)

# ====== Запуск ======
def run_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=8080)
