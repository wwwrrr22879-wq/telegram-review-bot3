import os
from datetime import datetime
from flask import Flask, request
import telebot
from telebot import types

# ====== Настройки ======
BOT_TOKEN = "8009524027:AAHTRgwiKnUi9AAh1_LTkekGZ-mRvNzH7dY"
OWNER_ID = 1470389051

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
    "pending": {}
}

# ====== Проверка владельца ======
def is_owner(user_id):
    return user_id == OWNER_ID

# ====== Главное меню ======
def main_menu_markup():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Оставить отзыв", "📊 Посмотреть репутацию", "🛠 Админ-меню")
    return kb

# ====== Команда /start ======
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(
        message.chat.id,
        "Привет! Я бот поддержки и отзывов 💌\nОставь свой отзыв или посмотри репутацию администратора.",
        reply_markup=main_menu_markup()
    )

# ====== Оставить отзыв ======
@bot.message_handler(func=lambda m: m.text == "Оставить отзыв")
def leave_review(message):
    bot.send_message(
        message.chat.id,
        "Напишите имя администратора с # в начале, например #Шерлок",
        reply_markup=types.ReplyKeyboardRemove()
    )
    reviews_db["pending"][str(message.from_user.id)] = {"step": "admin_name"}

@bot.message_handler(func=lambda m: str(m.from_user.id) in reviews_db.get("pending", {}))
def save_review(message):
    user_id = str(message.from_user.id)
    step_data = reviews_db["pending"][user_id]
    text = message.text.strip()

    # Шаг выбора админа
    if step_data["step"] == "admin_name":
        if not text.startswith("#"):
            bot.send_message(message.chat.id, "Пожалуйста, напишите # и имя администратора, например #Шерлок")
            return
        admin_key = text[1:].lower()
        step_data.update({"step": "stars", "key": admin_key, "display": text})
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        kb.add("1","2","3","4","5")
        bot.send_message(message.chat.id, "Сколько звезд? (1-5)", reply_markup=kb)
        return

    # Шаг выбора звезд
    if step_data["step"] == "stars":
        if text not in ["1","2","3","4","5"]:
            bot.send_message(message.chat.id, "Пожалуйста, выберите число от 1 до 5")
            return
        step_data.update({"step": "text", "stars": int(text)})
        bot.send_message(message.chat.id, "Если хотите оставить текстовый отзыв, напишите его. Если нет — напишите '-'")
        return

    # Шаг текстового отзыва
    if step_data["step"] == "text":
        stars = step_data["stars"]
        admin_key = step_data["key"]
        display_name = step_data["display"]
        review_text = "" if text == "-" else text
        entry = {
            "user": message.from_user.username or f"id{message.from_user.id}",
            "stars": stars,
            "text": review_text,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if admin_key not in reviews_db["admins"]:
            reviews_db["admins"][admin_key] = {"display": display_name, "reviews": []}

        reviews_db["admins"][admin_key]["reviews"].append(entry)
        del reviews_db["pending"][user_id]

        bot.send_message(message.chat.id, f"✅ Отзыв сохранён! {'⭐️'*stars}", reply_markup=main_menu_markup())

# ====== Просмотр рейтинга ======
@bot.message_handler(func=lambda m: m.text == "📊 Посмотреть репутацию")
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
        txt += f"{info['display']} — {'⭐️'*int(avg)} ({avg})\n"
        for r in reviews:
            stars = '⭐️' * r['stars']
            text = f" — {r['text']}" if r['text'] else ""
            txt += f"   • {r['user']}: {stars}{text}\n"
        txt += "\n"
    bot.send_message(message.chat.id, txt or "Пока нет отзывов.", reply_markup=main_menu_markup())

# ====== Админ-меню ======
@bot.message_handler(func=lambda m: m.text == "🛠 Админ-меню")
def admin_menu(message):
    if not is_owner(message.from_user.id):
        bot.send_message(message.chat.id, "⛔️ Доступ запрещён.", reply_markup=main_menu_markup())
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
            line = f"{i+1}. {r['user']} — {'⭐️'*r['stars']}"
            if r['text']:
                line += f" — {r['text']}"
            text.append(line)
            kb.add(types.InlineKeyboardButton(f"🗑 Удалить #{i+1}", callback_data=f"delrev|{key}|{i}"))
        bot.send_message(call.message.chat.id, "\n".join(text), reply_markup=kb)
    elif data[0] == "delrev":
        _, key, idx = data
        idx = int(idx)
        reviews = reviews_db.get("admins", {}).get(key, {}).get("reviews", [])
        if 0 <= idx < len(reviews):
            rem = reviews.pop(idx)
            bot.send_message(call.message.chat.id, f"✅ Удалено: {rem['user']} ({'⭐️'*rem['stars']})")
        else:
            bot.send_message(call.message.chat.id, "Отзыв не найден.")
    bot.answer_callback_query(call.id)

# ====== Webhook для Render ======
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def home():
    return "Бот работает ✅"

# ====== Установка webhook ======
if __name__ == "__main__":
    # Установи свой домен Render вместо <твой-домен>
    WEBHOOK_URL = "https://<твой-домен>/" + BOT_TOKEN
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
