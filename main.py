import os
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime
import threading

# ====== Настройки ======
BOT_TOKEN = "8009524027:AAHTRgwiKnUi9AAh1_LTkekGZ-mRvNzH7dY"  # Вставляй свій токен сюди
OWNER_ID = 1470389051  # Вставляй свій ID сюди

bot = telebot.TeleBot(BOT_TOKEN)

app = Flask(__name__)

# ====== База данных отзывов ======
reviews_db = {
    "admins": {
        "sherlock": {
            "display": "#Шерлок",
            "reviews": []
        }
    },
    "pending": {}  # Для временного хранения отзывов
}

# ====== Проверка владельца ======
def is_owner(user_id):
    return user_id == OWNER_ID

# ====== Сохранение отзывов ======
def save_db():
    # Тут можна додати збереження в файл, якщо потрібно
    pass

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def home():
    return "Бот работает ✅"

# ====== Обработчики ======

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "Привет! Я бот отзывов. Выберите команду из меню ниже.")

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
    bot.send_message(message.chat.id, f"✅ Отзыв сохранён! {'⭐️' * stars}")

@bot.message_handler(func=lambda m: m.text == "📊 Посмотреть рейтинг")
def show_ratings(message):
    if not reviews_db["admins"]:
        bot.send_message(message.chat.id, "Пока нет отзывов.")
        return
    txt = ""
    for k, info in reviews_db["admins"].items():
        reviews = info["reviews"]
        if not reviews:
            continue
        avg = round(sum(r["stars"] for r in reviews) / len(reviews), 2)
        txt += f"{info['display']} — {'⭐️' * int(avg)} ({avg})\n"
        for r in reviews:
            user = r['user']
            stars = '⭐️' * r['stars']
            text = f" — {r['text']}" if r['text'] else ""
            txt += f"   • {user}: {stars}{text}\n"
        txt += "\n"
    bot.send_message(message.chat.id, txt or "Пока нет отзывов.")

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-меню")
def admin_menu(message):
    if not is_owner(message.from_user.id):
        bot.send_message(message.chat.id, "⛔️ Доступ запрещён.")
        return
    kb = types.InlineKeyboardMarkup()
    for k, info in reviews_db["admins"].items():
        kb.add(types.InlineKeyboardButton(info["display"], callback_data=f"adm|{k}"))
    bot.send_message(message.chat.id, "Выберите администратора:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm|") or c.data.startswith("delrev|"))
def admin_actions(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "Нет доступа.")
        return
    data = call.data.split("|")
    if data[0] == "adm":
        key = data[1]
        info = reviews_db["admins"].get(key)
        if not info or not info["reviews"]:
            bot.send_message(call.message.chat.id, f"{key} — нет отзывов.")
            return
        kb = types.InlineKeyboardMarkup()
        text = [f"📋 Отзывы про {info['display']}:"]
        for i, r in enumerate(info["reviews"]):
            line = f"{i+1}. {r['user']} — {'⭐️' * r['stars']}"
            if r['text']:
                line += f" — {r['text']}"
            text.append(line)
            kb.add(types.InlineKeyboardButton(f"🗑 Удалить #{i+1}", callback_data=f"delrev|{key}|{i}"))
        bot.send_message(call.message.chat.id, "\n".join(text), reply_markup=kb)
    elif data[0] == "delrev":
        _, key, idx = data
        idx = int(idx)
        reviews = reviews_db["admins"].get(key, {}).get("reviews", [])
        if 0 <= idx < len(reviews):
            rem = reviews.pop(idx)
            save_db()
            bot.send_message(call.message.chat.id, f"✅ Удалено: {rem['user']} ({'⭐️'*rem['stars']})")
        else:
            bot.send_message(call.message.chat.id, "Отзыв не найден.")
        bot.answer_callback_query(call.id)

# ====== Запуск на Render ======
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://telegram-review-bo.onrender.com/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=8080)
