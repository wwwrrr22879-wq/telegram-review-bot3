import threading
from flask import Flask, request
import telebot
from telebot import types
from datetime import datetime

# ====== Настройки ======
BOT_TOKEN = "8009524027:AAHTRgwiKnUi9AAh1_LTkekGZ-mRvNzH7dY"
OWNER_ID = 1470389051

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ====== База данных отзывов ======
reviews_db = {
    "admins": {
        "sherlock": {"display": "#Шерлок", "reviews": []}
    },
    "pending": {}
}

# ====== Проверка владельца ======
def is_owner(user_id):
    return user_id == OWNER_ID

# ====== Стартовое меню ======
def main_keyboard(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📊 Посмотреть репутацию")
    kb.add("📝 Оставить отзыв")
    if user_id == OWNER_ID:
        kb.add("🛠 Админ-меню")
    return kb

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(
        message.chat.id,
        "Привет! Я бот отзывов, оставь свой отзыв через кнопки внизу 👇",
        reply_markup=main_keyboard(message.from_user.id)
    )

# ====== Начало отзыва ======
@bot.message_handler(func=lambda m: m.text == "📝 Оставить отзыв")
def start_review(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("#Шерлок")
    kb.add("Отмена")
    bot.send_message(message.chat.id, "Выберите администратора, используя # перед именем (например #Шерлок):", reply_markup=kb)

# ====== Выбор администратора ======
@bot.message_handler(func=lambda m: m.text.startswith("#"))
def select_admin(message):
    admin_key = message.text[1:].lower()  # убираем # и приводим к lower
    if admin_key != "sherlock":
        bot.send_message(message.chat.id, "❌ Такой админ не найден. Напишите # перед именем, например #Шерлок")
        return
    user_id = str(message.from_user.id)
    reviews_db["pending"][user_id] = {"key": admin_key, "stars": 0, "text": ""}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i in range(1, 6):
        kb.add(str(i))
    bot.send_message(message.chat.id, f"Вы выбрали {reviews_db['admins'][admin_key]['display']}. Теперь выберите количество ⭐️ (1-5):", reply_markup=kb)

# ====== Выбор звезд ======
@bot.message_handler(func=lambda m: str(m.from_user.id) in reviews_db["pending"] and m.text in ["1","2","3","4","5"])
def select_stars(message):
    user_id = str(message.from_user.id)
    reviews_db["pending"][user_id]["stars"] = int(message.text)
    bot.send_message(message.chat.id, "Если хотите оставить текстовый отзыв об админе, напишите его. Если нет, напишите '-'")
    
# ====== Ввод текста ======
@bot.message_handler(func=lambda m: str(m.from_user.id) in reviews_db["pending"])
def enter_text_review(message):
    user_id = str(message.from_user.id)
    if reviews_db["pending"][user_id]["stars"] == 0:
        # пользователь еще не выбрал звезды
        return
    text = message.text.strip()
    if not text:
        text = "-"
    reviews_db["pending"][user_id]["text"] = text
    data = reviews_db["pending"].pop(user_id)
    entry = {
        "user": message.from_user.username or f"id{message.from_user.id}",
        "stars": data["stars"],
        "text": "" if data["text"] == "-" else data["text"],
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    reviews_db["admins"][data["key"]]["reviews"].append(entry)
    bot.send_message(message.chat.id, f"✅ Отзыв оставлен! {'⭐️'*entry['stars']}", reply_markup=main_keyboard(message.from_user.id))

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
            user = r['user']
            stars = '⭐️'*r['stars']
            text = f" — {r['text']}" if r['text'] else ""
            txt += f"   • {user}: {stars}{text}\n"
        txt += "\n"
    bot.send_message(message.chat.id, txt or "Пока нет отзывов.")

# ====== Админ-меню ======
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
            line = f"{i+1}. {r['user']} — {'⭐️'*r['stars']}"
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
    return "!", 200

@app.route("/")
def home():
    return "Бот работает ✅"

# ====== Запуск ======
def run_bot():
    bot.remove_webhook()  # видаляємо старий webhook
    bot.infinity_polling(timeout=60, long_polling_timeout=60)

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=8080)
