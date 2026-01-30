"""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║           📱 TELEGRAM HOMEWORK BOT 📚                ║
║                                                      ║
║              Made by @romasent ⭐                    ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
"""

print("=" * 54)
print("║           📱 TELEGRAM HOMEWORK BOT 📚                ║")
print("║              Made by @romasent ⭐                    ║")
print("=" * 54)
print()

import asyncio
import json
import sqlite3
import time
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

class RateBot(StatesGroup):
    rate = State()

class BanUser(StatesGroup):
    user_id = State()
    duration = State()

class PromoCode(StatesGroup):
    code = State()

class AddPromoCode(StatesGroup):
    code = State()
    type = State()
    content = State()
    max_uses = State()
    
# ================= НАСТРОЙКИ =================
TOKEN = "8585476552:AAFCXmjcCR96IbYyDzt6MzlR1bdngRWQ714"
ADMIN_ID = 1425386076  # твой telegram id

DB_FILE = "bot.db"
SCHOOL_FILE = "school_list.json"

SUBJECTS = {
    "Русский язык": 6,
    "Математический анализ (профиль)": 5,
    "Химия": 2,
    "Английский язык": 3,
    "Физика": 3,
    "Математический анализ (база)": 2,
    "Информатика": 3,
    "История": 1,
    "География": 1,
    "Биология": 1,
    "Литература": 1,
    "Обществознание": 2
}

# Короткие ID для callback_data (чтобы не превышать лимит Telegram)
SUBJECT_IDS = {name: idx for idx, name in enumerate(SUBJECTS.keys())}
ID_TO_SUBJECT = {idx: name for name, idx in SUBJECT_IDS.items()}

bot = Bot(TOKEN)
dp = Dispatcher()

# ================= БАЗА ДАННЫХ =================
db = sqlite3.connect(DB_FILE)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    class TEXT,
    bot_rated INTEGER DEFAULT 0,
    rating INTEGER DEFAULT 0,
    uploaded_count INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    subject TEXT,
    group_num INTEGER,
    file_id TEXT,
    created_at TEXT,
    reported INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id INTEGER,
    reporter_id INTEGER,
    created_at INTEGER,
    reason TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS bans (
    user_id INTEGER PRIMARY KEY,
    until INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS likes (
    user_id INTEGER,
    photo_id INTEGER,
    PRIMARY KEY (user_id, photo_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS promocodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    type TEXT,
    content TEXT,
    uses INTEGER DEFAULT 0,
    max_uses INTEGER DEFAULT -1,
    active INTEGER DEFAULT 1
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS promocode_uses (
    user_id INTEGER,
    code TEXT,
    used_at INTEGER,
    PRIMARY KEY (user_id, code)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS secret_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT UNIQUE COLLATE NOCASE,
    response TEXT,
    created_at INTEGER
)
""")

db.commit()

# ================= FSM =================
class Register(StatesGroup):
    first_name = State()
    last_name = State()
    class_name = State()

class UploadPhoto(StatesGroup):
    subject = State()
    photo = State()
    group = State()

class ReportPhoto(StatesGroup):
    reason = State()

class SecretCode(StatesGroup):
    waiting_text = State()

class AddSecret(StatesGroup):
    trigger = State()
    response = State()

# ================= КНОПКИ =================
def menu_kb(is_admin=False):
    kb = [
        [KeyboardButton(text="📤 Загрузить фото")],
        [KeyboardButton(text="📚 Смотреть фото")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🏆 Топ")],
        [KeyboardButton(text="🎁 Промокоды"), KeyboardButton(text="⭐ Оценить бота")],
        [KeyboardButton(text="🔐 Секретная зона")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Все фото")],
            [KeyboardButton(text="🚨 Фото с жалобами")],
            [KeyboardButton(text="👥 Список пользователей")],
            [KeyboardButton(text="🚫 Забанить по ID")],
            [KeyboardButton(text="🎁 Управление промокодами")],
            [KeyboardButton(text="🔐 Секретные ответы")],
            [KeyboardButton(text="🏠 В меню")]
        ],
        resize_keyboard=True
    )

def back_kb(callback_data="back_menu"):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)]
        ]
    )

def subjects_kb(prefix="sub"):
    buttons = []
    for s in SUBJECTS:
        buttons.append([InlineKeyboardButton(text=s, callback_data=f"{prefix}:{SUBJECT_IDS[s]}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def groups_kb(subject_id, prefix="g"):
    subject = ID_TO_SUBJECT[subject_id]
    buttons = []
    for i in range(1, SUBJECTS[subject] + 1):
        buttons.append([InlineKeyboardButton(
            text=f"Группа {i}",
            callback_data=f"{prefix}:{subject_id}:{i}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_subjects_{prefix}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def photo_actions_kb(photo_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍 Лайк", callback_data=f"like:{photo_id}"),
                InlineKeyboardButton(text="🚨 Пожаловаться", callback_data=f"report:{photo_id}")
            ]
        ]
    )

def admin_photo_kb(photo_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить фото", callback_data=f"del:{photo_id}")],
        [
            InlineKeyboardButton(text="🚫 Бан 30м", callback_data=f"ban:{photo_id}:1800"),
            InlineKeyboardButton(text="🚫 Бан 1ч", callback_data=f"ban:{photo_id}:3600")
        ],
        [
            InlineKeyboardButton(text="🚫 Бан 1д", callback_data=f"ban:{photo_id}:86400"),
            InlineKeyboardButton(text="🚫 Бан 7д", callback_data=f"ban:{photo_id}:604800")
        ]
    ])

# ================= ЛИМИТЫ =================
last_message_time = {}
last_complaint_time = {}

def is_spam(user_id):
    now = time.time()
    if user_id in last_message_time and now - last_message_time[user_id] < 5:
        return True
    last_message_time[user_id] = now
    return False

def can_complain(user_id):
    now = time.time()
    if user_id in last_complaint_time and now - last_complaint_time[user_id] < 300:  # 5 минут
        return False
    last_complaint_time[user_id] = now
    return True

def is_banned(user_id):
    cur.execute("SELECT until FROM bans WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row and row[0] > int(time.time()):
        return True
    elif row:
        # Удаляем истекший бан
        cur.execute("DELETE FROM bans WHERE user_id = ?", (user_id,))
        db.commit()
    return False

# ================= /start и РЕГИСТРАЦИЯ =================
@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    if is_spam(message.from_user.id):
        return
    if is_banned(message.from_user.id):
        await message.answer("⛔ Вы временно заблокированы")
        return

    cur.execute("SELECT tg_id FROM users WHERE tg_id = ?", (message.from_user.id,))
    if cur.fetchone():
        await message.answer("🏠 Главное меню", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
        return

    await message.answer(
        "╔══════════════════════════════════╗\n"
        "║  📱 HOMEWORK BOT 📚              ║\n"
        "║                                  ║\n"
        "║  Made by @romasent ⭐            ║\n"
        "╚══════════════════════════════════╝\n\n"
        "Добро пожаловать! 👋\n\n"
        "Введите ваше имя:"
    )
    await state.set_state(Register.first_name)

@dp.message(Register.first_name)
async def reg_first(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text.strip())
    await message.answer("Введите фамилию:")
    await state.set_state(Register.last_name)

@dp.message(Register.last_name)
async def reg_last(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text.strip())
    await message.answer("Введите класс (например: 11А):")
    await state.set_state(Register.class_name)

@dp.message(Register.class_name)
async def reg_class(message: Message, state: FSMContext):
    data = await state.get_data()

    try:
        with open(SCHOOL_FILE, encoding="utf-8") as f:
            school = json.load(f)
    except:
        school = []

    found = any(
        s["first_name"].lower() == data["first_name"].lower()
        and s["last_name"].lower() == data["last_name"].lower()
        and s["class"].lower() == message.text.lower()
        for s in school
    )

    if not found:
        await message.answer("❌ Вас нет в списке школы")
        await state.clear()
        return

    cur.execute(
        "INSERT INTO users (tg_id, first_name, last_name, class) VALUES (?, ?, ?, ?)",
        (message.from_user.id, data["first_name"], data["last_name"], message.text)
    )
    db.commit()

    await message.answer("✅ Регистрация успешна!", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
    await state.clear()

# ================= КНОПКА НАЗАД =================
@dp.callback_query(F.data == "back_menu")
async def back_to_menu_callback(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("🏠 Главное меню", reply_markup=menu_kb(call.from_user.id == ADMIN_ID))
    await call.answer()

@dp.callback_query(F.data.startswith("back_subjects_"))
async def back_to_subjects(call: CallbackQuery):
    prefix = call.data.split("_")[-1]
    if prefix == "g":  # Загрузка фото
        await call.message.edit_text("Выберите предмет:", reply_markup=subjects_kb("sub"))
    elif prefix == "vg":  # Просмотр фото
        await call.message.edit_text("Выберите предмет:", reply_markup=subjects_kb("vs"))
    await call.answer()

# ================= В МЕНЮ =================
@dp.message(F.text == "🏠 В меню")
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Главное меню", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))

# ================= ПРОФИЛЬ =================
@dp.message(F.text == "👤 Профиль")
async def profile(message: Message):
    cur.execute(
        "SELECT first_name, last_name, class, rating, uploaded_count FROM users WHERE tg_id = ?",
        (message.from_user.id,)
    )
    u = cur.fetchone()
    if u:
        await message.answer(
            f"👤 <b>{u[0]} {u[1]}</b>\n"
            f"🏫 Класс: {u[2]}\n"
            f"⭐ Рейтинг: {u[3]} 👍\n"
            f"📤 Загружено фото: {u[4]}\n\n"
            f"<i>Made by @romasent</i>",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Профиль не найден. Используйте /start для регистрации")

# ================= ТОП ПОЛЬЗОВАТЕЛЕЙ =================
@dp.message(F.text == "🏆 Топ")
async def top_users(message: Message):
    cur.execute(
        "SELECT first_name, last_name, rating, uploaded_count FROM users ORDER BY rating DESC LIMIT 10"
    )
    users = cur.fetchall()
    
    if not users:
        await message.answer("📊 Пока нет данных")
        return
    
    text = "🏆 <b>Топ пользователей по рейтингу:</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for idx, (fname, lname, rating, count) in enumerate(users, 1):
        medal = medals[idx-1] if idx <= 3 else f"{idx}."
        text += f"{medal} {fname} {lname}\n"
        text += f"   ⭐ {rating} 👍 | 📤 {count} фото\n\n"
    
    await message.answer(text, parse_mode="HTML")

# ================= ЗАГРУЗКА ФОТО =================
@dp.message(F.text == "📤 Загрузить фото")
async def upload_start(message: Message, state: FSMContext):
    await message.answer("Выберите предмет:", reply_markup=subjects_kb("sub"))
    await state.set_state(UploadPhoto.subject)

@dp.callback_query(F.data.startswith("sub:"))
async def upload_subject(call: CallbackQuery, state: FSMContext):
    subject_id = int(call.data.split(":", 1)[1])
    subject = ID_TO_SUBJECT[subject_id]
    await state.update_data(subject=subject, subject_id=subject_id)
    await call.message.edit_text(
        f"📚 Предмет: {subject}\n\nВыберите группу:",
        reply_markup=groups_kb(subject_id, "g")
    )
    await call.answer()

@dp.callback_query(F.data.startswith("g:"))
async def upload_select_group(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    subject_id = int(parts[1])
    group = int(parts[2])
    subject = ID_TO_SUBJECT[subject_id]
    
    await state.update_data(group=group)
    await call.message.delete()
    await call.message.answer(
        f"📚 Предмет: {subject}\n👥 Группа: {group}\n\n📷 Отправьте фото:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 В меню")]],
            resize_keyboard=True
        )
    )
    await state.set_state(UploadPhoto.photo)
    await call.answer()

@dp.message(UploadPhoto.photo, F.photo)
async def upload_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    
    cur.execute(
        "INSERT INTO photos (user_id, subject, group_num, file_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            message.from_user.id,
            data["subject"],
            data["group"],
            message.photo[-1].file_id,
            datetime.now().strftime("%d.%m.%Y %H:%M")
        )
    )
    
    # Увеличиваем счётчик загрузок
    cur.execute(
        "UPDATE users SET uploaded_count = uploaded_count + 1 WHERE tg_id = ?",
        (message.from_user.id,)
    )
    db.commit()

    await message.answer("✅ Фото загружено!", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
    await state.clear()

# ================= ПРОСМОТР ФОТО =================
@dp.message(F.text == "📚 Смотреть фото")
async def view_start(message: Message):
    await message.answer("Выберите предмет:", reply_markup=subjects_kb("vs"))

@dp.callback_query(F.data.startswith("vs:"))
async def view_select_subject(call: CallbackQuery):
    subject_id = int(call.data.split(":", 1)[1])
    subject = ID_TO_SUBJECT[subject_id]
    await call.message.edit_text(
        f"📚 Предмет: {subject}\n\nВыберите группу:",
        reply_markup=groups_kb(subject_id, "vg")
    )
    await call.answer()

@dp.callback_query(F.data.startswith("vg:"))
async def view_photos(call: CallbackQuery):
    parts = call.data.split(":")
    subject_id = int(parts[1])
    group = parts[2]
    subject = ID_TO_SUBJECT[subject_id]
    
    cur.execute(
        """SELECT p.id, p.file_id, p.created_at, p.likes, u.first_name, u.last_name 
           FROM photos p
           JOIN users u ON p.user_id = u.tg_id
           WHERE p.subject=? AND p.group_num=?
           ORDER BY p.created_at DESC""",
        (subject, int(group))
    )
    photos = cur.fetchall()

    if not photos:
        await call.message.answer("📭 Фото пока нет")
        await call.answer()
        return

    await call.message.delete()
    for pid, fid, created, likes, fname, lname in photos:
        await bot.send_photo(
            call.from_user.id,
            fid,
            caption=f"📚 {subject} | 👥 Группа {group}\n"
                    f"👤 {fname} {lname}\n"
                    f"🕒 {created}\n"
                    f"👍 {likes} лайков",
            reply_markup=photo_actions_kb(pid)
        )
    await call.answer()

# ================= ЛАЙКИ =================
@dp.callback_query(F.data.startswith("like:"))
async def like_photo(call: CallbackQuery):
    photo_id = int(call.data.split(":")[1])
    user_id = call.from_user.id
    
    # Проверяем, ставил ли пользователь уже лайк
    cur.execute("SELECT * FROM likes WHERE user_id = ? AND photo_id = ?", (user_id, photo_id))
    if cur.fetchone():
        await call.answer("❤️ Вы уже поставили лайк!", show_alert=True)
        return
    
    # Получаем ID автора фото
    cur.execute("SELECT user_id FROM photos WHERE id = ?", (photo_id,))
    author = cur.fetchone()
    if not author:
        await call.answer("❌ Фото не найдено")
        return
    
    author_id = author[0]
    
    # Добавляем лайк
    cur.execute("INSERT INTO likes (user_id, photo_id) VALUES (?, ?)", (user_id, photo_id))
    cur.execute("UPDATE photos SET likes = likes + 1 WHERE id = ?", (photo_id,))
    cur.execute("UPDATE users SET rating = rating + 1 WHERE tg_id = ?", (author_id,))
    db.commit()
    
    # Обновляем счётчик лайков в сообщении
    cur.execute("SELECT likes FROM photos WHERE id = ?", (photo_id,))
    new_likes = cur.fetchone()[0]
    
    # Обновляем caption
    old_caption = call.message.caption
    lines = old_caption.split('\n')
    lines[-1] = f"👍 {new_likes} лайков"
    new_caption = '\n'.join(lines)
    
    await call.message.edit_caption(
        caption=new_caption,
        reply_markup=photo_actions_kb(photo_id)
    )
    await call.answer("👍 Лайк поставлен!")

# ================= ЖАЛОБЫ =================
@dp.callback_query(F.data.startswith("report:"))
async def report_photo_start(call: CallbackQuery, state: FSMContext):
    photo_id = int(call.data.split(":")[1])

    if not can_complain(call.from_user.id):
        await call.answer("⏳ Можно жаловаться раз в 5 минут", show_alert=True)
        return

    await state.update_data(photo_id=photo_id)
    await call.message.answer(
        "🚨 <b>Отправка жалобы</b>\n\n"
        "Укажите причину жалобы:\n"
        "• Неправильный предмет\n"
        "• Плохое качество\n"
        "• Неподходящий контент\n"
        "• Другое\n\n"
        "Напишите причину:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 В меню")]],
            resize_keyboard=True
        )
    )
    await state.set_state(ReportPhoto.reason)
    await call.answer()

@dp.message(ReportPhoto.reason)
async def report_photo_finish(message: Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
        return
    
    data = await state.get_data()
    photo_id = data["photo_id"]
    reason = message.text.strip()
    
    cur.execute(
        "INSERT INTO reports (photo_id, reporter_id, created_at, reason) VALUES (?, ?, ?, ?)",
        (photo_id, message.from_user.id, int(time.time()), reason)
    )
    cur.execute("UPDATE photos SET reported = 1 WHERE id = ?", (photo_id,))
    db.commit()

    await message.answer("✅ Жалоба отправлена администратору", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
    
    # Уведомляем админа
    try:
        cur.execute(
            """SELECT p.subject, p.group_num, u.first_name, u.last_name, u.tg_id
               FROM photos p
               JOIN users u ON p.user_id = u.tg_id
               WHERE p.id = ?""",
            (photo_id,)
        )
        info = cur.fetchone()
        if info:
            await bot.send_message(
                ADMIN_ID,
                f"🚨 <b>Новая жалоба!</b>\n\n"
                f"📚 Предмет: {info[0]}\n"
                f"👥 Группа: {info[1]}\n"
                f"👤 Автор: {info[2]} {info[3]} (ID: {info[4]})\n"
                f"📝 Причина: {reason}\n"
                f"🆔 ID фото: {photo_id}",
                parse_mode="HTML"
            )
    except:
        pass
    
    await state.clear()

# ================= ОЦЕНКА БОТА =================
@dp.message(F.text == "⭐ Оценить бота")
async def rate_start(message: Message, state: FSMContext):
    await message.answer(
        "Оцените бота от 1 до 5 ⭐",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 В меню")]],
            resize_keyboard=True
        )
    )
    await state.set_state(RateBot.rate)

@dp.message(RateBot.rate)
async def rate_finish(message: Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
        return
        
    if message.text not in ["1", "2", "3", "4", "5"]:
        await message.answer("❌ Введите число от 1 до 5")
        return

    await bot.send_message(
        ADMIN_ID,
        f"⭐ <b>Оценка бота</b>\n"
        f"👤 ID: {message.from_user.id}\n"
        f"Оценка: {message.text} ⭐",
        parse_mode="HTML"
    )
    await message.answer("Спасибо за оценку ❤️", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
    await state.clear()

# ================= ПРОМОКОДЫ (ПОЛЬЗОВАТЕЛИ) =================
@dp.message(F.text == "🎁 Промокоды")
async def promo_start(message: Message, state: FSMContext):
    await message.answer(
        "🎁 <b>Промокоды</b>\n\n"
        "Введите промокод для активации:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 В меню")]],
            resize_keyboard=True
        )
    )
    await state.set_state(PromoCode.code)

@dp.message(PromoCode.code)
async def promo_activate(message: Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
        return
    
    code = message.text.strip().upper()
    
    # Проверяем существование промокода
    cur.execute(
        "SELECT id, type, content, uses, max_uses, active FROM promocodes WHERE code = ?",
        (code,)
    )
    promo = cur.fetchone()
    
    if not promo:
        await message.answer("❌ Промокод не найден", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
        await state.clear()
        return
    
    promo_id, promo_type, content, uses, max_uses, active = promo
    
    # Проверяем активность
    if not active:
        await message.answer("❌ Промокод деактивирован", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
        await state.clear()
        return
    
    # Проверяем лимит использований
    if max_uses != -1 and uses >= max_uses:
        await message.answer("❌ Промокод исчерпан", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
        await state.clear()
        return
    
    # Проверяем, использовал ли пользователь уже этот промокод
    cur.execute(
        "SELECT * FROM promocode_uses WHERE user_id = ? AND code = ?",
        (message.from_user.id, code)
    )
    if cur.fetchone():
        await message.answer("❌ Вы уже использовали этот промокод", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
        await state.clear()
        return
    
    # Активируем промокод
    cur.execute("UPDATE promocodes SET uses = uses + 1 WHERE id = ?", (promo_id,))
    cur.execute(
        "INSERT INTO promocode_uses (user_id, code, used_at) VALUES (?, ?, ?)",
        (message.from_user.id, code, int(time.time()))
    )
    db.commit()
    
    # Отправляем награду
    if promo_type == "text":
        await message.answer(
            f"✅ <b>Промокод активирован!</b>\n\n{content}",
            parse_mode="HTML",
            reply_markup=menu_kb(message.from_user.id == ADMIN_ID)
        )
    elif promo_type == "image":
        try:
            await bot.send_photo(
                message.chat.id,
                content,
                caption="✅ <b>Промокод активирован!</b>",
                parse_mode="HTML",
                reply_markup=menu_kb(message.from_user.id == ADMIN_ID)
            )
        except:
            await message.answer("❌ Ошибка загрузки изображения", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
    
    await state.clear()

# ================= АДМИН-ПАНЕЛЬ =================
@dp.message(F.text == "🛠 Админ-панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🛠 Админ-панель", reply_markup=admin_kb())

@dp.message(F.text == "📸 Все фото")
async def admin_all_photos(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cur.execute(
        """SELECT p.id, p.file_id, p.subject, p.group_num, p.likes, u.first_name, u.last_name, u.tg_id
           FROM photos p
           JOIN users u ON p.user_id = u.tg_id
           ORDER BY p.created_at DESC
           LIMIT 20"""
    )
    photos = cur.fetchall()

    if not photos:
        await message.answer("📭 Фото нет")
        return

    for pid, fid, subj, grp, likes, fname, lname, user_id in photos:
        await bot.send_photo(
            message.chat.id,
            fid,
            caption=f"📚 {subj} | 👥 Группа {grp}\n"
                    f"👤 {fname} {lname} (ID: {user_id})\n"
                    f"👍 {likes} лайков\n"
                    f"🆔 ID фото: {pid}",
            reply_markup=admin_photo_kb(pid)
        )

@dp.message(F.text == "🚨 Фото с жалобами")
async def admin_reported_photos(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cur.execute("""
        SELECT DISTINCT p.id, p.file_id, p.subject, p.group_num, u.first_name, u.last_name, u.tg_id,
               (SELECT COUNT(*) FROM reports WHERE photo_id = p.id) as report_count
        FROM reports r
        JOIN photos p ON p.id = r.photo_id
        JOIN users u ON p.user_id = u.tg_id
        ORDER BY report_count DESC
    """)
    photos = cur.fetchall()

    if not photos:
        await message.answer("✅ Жалоб нет")
        return

    for pid, fid, subj, grp, fname, lname, user_id, report_count in photos:
        # Получаем последние жалобы
        cur.execute(
            "SELECT reason FROM reports WHERE photo_id = ? ORDER BY created_at DESC LIMIT 3",
            (pid,)
        )
        reasons = [r[0] for r in cur.fetchall()]
        reasons_text = "\n".join([f"• {r}" for r in reasons])
        
        await bot.send_photo(
            message.chat.id,
            fid,
            caption=f"🚨 <b>Жалоба ({report_count})</b>\n\n"
                    f"📚 {subj} | 👥 Группа {grp}\n"
                    f"👤 {fname} {lname} (ID: {user_id})\n"
                    f"🆔 ID фото: {pid}\n\n"
                    f"<b>Причины:</b>\n{reasons_text}",
            reply_markup=admin_photo_kb(pid),
            parse_mode="HTML"
        )

@dp.message(F.text == "👥 Список пользователей")
async def admin_users_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cur.execute(
        "SELECT first_name, last_name, class, tg_id, rating, uploaded_count FROM users ORDER BY rating DESC LIMIT 30"
    )
    users = cur.fetchall()

    if not users:
        await message.answer("📭 Пользователей нет")
        return

    text = "👥 <b>Список пользователей:</b>\n\n"
    for fname, lname, cls, uid, rating, count in users:
        text += f"👤 {fname} {lname} ({uid})\n"
        text += f"   🏫 {cls} | ⭐ {rating} | 📤 {count}\n\n"

    # Разбиваем на части, если слишком длинное
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.answer(part, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🚫 Забанить по ID")
async def admin_ban_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer(
        "🚫 <b>Бан пользователя</b>\n\n"
        "Введите Telegram ID пользователя:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 В меню")]],
            resize_keyboard=True
        )
    )
    await state.set_state(BanUser.user_id)

@dp.message(BanUser.user_id)
async def admin_ban_duration(message: Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await state.clear()
        await message.answer("🛠 Админ-панель", reply_markup=admin_kb())
        return
    
    if not message.text.isdigit():
        await message.answer("❌ ID должен быть числом")
        return
    
    user_id = int(message.text)
    
    # Проверяем существование пользователя
    cur.execute("SELECT first_name, last_name FROM users WHERE tg_id = ?", (user_id,))
    user = cur.fetchone()
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    await state.update_data(ban_user_id=user_id, user_name=f"{user[0]} {user[1]}")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="30 минут", callback_data="bandur:1800"),
            InlineKeyboardButton(text="1 час", callback_data="bandur:3600")
        ],
        [
            InlineKeyboardButton(text="1 день", callback_data="bandur:86400"),
            InlineKeyboardButton(text="7 дней", callback_data="bandur:604800")
        ],
        [
            InlineKeyboardButton(text="30 дней", callback_data="bandur:2592000"),
            InlineKeyboardButton(text="Навсегда", callback_data="bandur:999999999")
        ]
    ])
    
    await message.answer(
        f"👤 <b>{user[0]} {user[1]}</b> (ID: {user_id})\n\n"
        f"Выберите длительность бана:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(BanUser.duration)

@dp.callback_query(F.data.startswith("bandur:"))
async def admin_ban_confirm(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    user_id = data["ban_user_id"]
    user_name = data["user_name"]
    seconds = int(call.data.split(":")[1])
    
    until = int(time.time()) + seconds
    cur.execute("INSERT OR REPLACE INTO bans (user_id, until) VALUES (?, ?)", (user_id, until))
    db.commit()
    
    duration_text = {
        1800: "30 минут",
        3600: "1 час",
        86400: "1 день",
        604800: "7 дней",
        2592000: "30 дней",
        999999999: "навсегда"
    }.get(seconds, f"{seconds} секунд")
    
    await call.message.edit_text(
        f"✅ <b>Пользователь забанен</b>\n\n"
        f"👤 {user_name} (ID: {user_id})\n"
        f"⏰ Длительность: {duration_text}",
        parse_mode="HTML"
    )
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            user_id,
            f"⛔ Вы были заблокированы на {duration_text}"
        )
    except:
        pass
    
    await state.clear()
    await call.answer("🚫 Бан выдан")

# ================= УПРАВЛЕНИЕ ПРОМОКОДАМИ (АДМИН) =================
@dp.message(F.text == "🎁 Управление промокодами")
async def admin_promo_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать промокод")],
            [KeyboardButton(text="📋 Список промокодов")],
            [KeyboardButton(text="🏠 В меню")]
        ],
        resize_keyboard=True
    )
    await message.answer("🎁 <b>Управление промокодами</b>", reply_markup=kb, parse_mode="HTML")

@dp.message(F.text == "📋 Список промокодов")
async def admin_promo_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    cur.execute(
        "SELECT code, type, uses, max_uses, active FROM promocodes ORDER BY id DESC"
    )
    promos = cur.fetchall()
    
    if not promos:
        await message.answer("📭 Промокодов нет")
        return
    
    text = "📋 <b>Список промокодов:</b>\n\n"
    for code, ptype, uses, max_uses, active in promos:
        status = "✅" if active else "❌"
        limit = f"{uses}/{max_uses}" if max_uses != -1 else f"{uses}/∞"
        icon = "💬" if ptype == "text" else "🖼️"
        text += f"{status} <code>{code}</code> {icon}\n"
        text += f"   Использований: {limit}\n\n"
    
    # Добавляем кнопки для управления
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить промокод", callback_data="promo_delete_menu")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.message(F.text == "➕ Создать промокод")
async def admin_add_promo_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer(
        "🎁 <b>Создание промокода</b>\n\n"
        "Введите код промокода (например: HELLO2025):",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 В меню")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AddPromoCode.code)

@dp.message(AddPromoCode.code)
async def admin_add_promo_type(message: Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await state.clear()
        await message.answer("🛠 Админ-панель", reply_markup=admin_kb())
        return
    
    code = message.text.strip().upper()
    
    # Проверяем уникальность
    cur.execute("SELECT code FROM promocodes WHERE code = ?", (code,))
    if cur.fetchone():
        await message.answer("❌ Такой промокод уже существует")
        return
    
    await state.update_data(code=code)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Текст", callback_data="promo_type:text")],
        [InlineKeyboardButton(text="🖼️ Картинка", callback_data="promo_type:image")]
    ])
    
    await message.answer(
        f"Промокод: <code>{code}</code>\n\n"
        "Выберите тип награды:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(AddPromoCode.type)

@dp.callback_query(F.data.startswith("promo_type:"))
async def admin_add_promo_content(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    
    promo_type = call.data.split(":")[1]
    await state.update_data(promo_type=promo_type)
    
    if promo_type == "text":
        await call.message.answer(
            "💬 Введите текст, который получит пользователь:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🏠 В меню")]],
                resize_keyboard=True
            )
        )
    else:
        await call.message.answer(
            "🖼️ Отправьте изображение, которое получит пользователь:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🏠 В меню")]],
                resize_keyboard=True
            )
        )
    
    await state.set_state(AddPromoCode.content)
    await call.answer()

@dp.message(AddPromoCode.content)
async def admin_add_promo_max_uses(message: Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await state.clear()
        await message.answer("🛠 Админ-панель", reply_markup=admin_kb())
        return
    
    data = await state.get_data()
    
    if data["promo_type"] == "text":
        content = message.text
    elif message.photo:
        content = message.photo[-1].file_id
    else:
        await message.answer("❌ Отправьте изображение")
        return
    
    await state.update_data(content=content)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 раз", callback_data="promo_max:1"),
            InlineKeyboardButton(text="5 раз", callback_data="promo_max:5")
        ],
        [
            InlineKeyboardButton(text="10 раз", callback_data="promo_max:10"),
            InlineKeyboardButton(text="50 раз", callback_data="promo_max:50")
        ],
        [
            InlineKeyboardButton(text="∞ Без ограничений", callback_data="promo_max:-1")
        ]
    ])
    
    await message.answer(
        "Выберите максимальное количество использований:",
        reply_markup=kb
    )
    await state.set_state(AddPromoCode.max_uses)

@dp.callback_query(F.data.startswith("promo_max:"))
async def admin_add_promo_finish(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    
    max_uses = int(call.data.split(":")[1])
    data = await state.get_data()
    
    # Создаём промокод
    cur.execute(
        "INSERT INTO promocodes (code, type, content, max_uses) VALUES (?, ?, ?, ?)",
        (data["code"], data["promo_type"], data["content"], max_uses)
    )
    db.commit()
    
    limit_text = f"{max_uses} раз" if max_uses != -1 else "без ограничений"
    type_icon = "💬" if data["promo_type"] == "text" else "🖼️"
    
    await call.message.edit_text(
        f"✅ <b>Промокод создан!</b>\n\n"
        f"🎁 Код: <code>{data['code']}</code>\n"
        f"{type_icon} Тип: {data['promo_type']}\n"
        f"📊 Лимит: {limit_text}",
        parse_mode="HTML"
    )
    
    await state.clear()
    await call.answer("✅ Промокод создан")

@dp.callback_query(F.data == "promo_delete_menu")
async def admin_promo_delete_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    cur.execute("SELECT code FROM promocodes WHERE active = 1 ORDER BY id DESC LIMIT 10")
    promos = cur.fetchall()
    
    if not promos:
        await call.answer("Нет активных промокодов", show_alert=True)
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗑 {code[0]}", callback_data=f"promo_del:{code[0]}")]
        for code in promos
    ])
    
    await call.message.edit_text(
        "🗑 <b>Удаление промокода</b>\n\nВыберите промокод для удаления:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("promo_del:"))
async def admin_promo_delete_confirm(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    code = call.data.split(":", 1)[1]
    
    cur.execute("DELETE FROM promocodes WHERE code = ?", (code,))
    cur.execute("DELETE FROM promocode_uses WHERE code = ?", (code,))
    db.commit()
    
    await call.message.edit_text(
        f"✅ Промокод <code>{code}</code> удалён",
        parse_mode="HTML"
    )
    await call.answer("🗑 Промокод удалён")

# ================= УДАЛЕНИЕ ФОТО =================
@dp.callback_query(F.data.startswith("del:"))
async def delete_photo(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    photo_id = int(call.data.split(":")[1])
    
    # Получаем ID автора перед удалением
    cur.execute("SELECT user_id, likes FROM photos WHERE id = ?", (photo_id,))
    result = cur.fetchone()
    if result:
        author_id, likes = result
        # Уменьшаем рейтинг автора на количество лайков
        cur.execute("UPDATE users SET rating = rating - ?, uploaded_count = uploaded_count - 1 WHERE tg_id = ?", (likes, author_id))
    
    cur.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    cur.execute("DELETE FROM reports WHERE photo_id = ?", (photo_id,))
    cur.execute("DELETE FROM likes WHERE photo_id = ?", (photo_id,))
    db.commit()

    await call.message.delete()
    await call.answer("🗑 Фото удалено")

# ================= БАН АВТОРА ФОТО =================
@dp.callback_query(F.data.startswith("ban:"))
async def ban_user(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    _, photo_id, seconds = call.data.split(":")
    seconds = int(seconds)

    cur.execute("SELECT user_id FROM photos WHERE id = ?", (photo_id,))
    result = cur.fetchone()
    
    if not result:
        await call.answer("❌ Фото не найдено")
        return
    
    user_id = result[0]

    until = int(time.time()) + seconds
    cur.execute("INSERT OR REPLACE INTO bans (user_id, until) VALUES (?, ?)", (user_id, until))
    db.commit()

    duration = {
        1800: "30 минут",
        3600: "1 час",
        86400: "1 день",
        604800: "7 дней"
    }.get(seconds, f"{seconds//60} минут")

    await call.answer(f"🚫 Автор забанен на {duration}")
    
    # Уведомляем пользователя
    try:
        await bot.send_message(user_id, f"⛔ Вы были заблокированы на {duration}")
    except:
        pass

# ================= СЕКРЕТНАЯ ЗОНА =================
@dp.message(F.text == "🔐 Секретная зона")
async def secret_zone(message: Message, state: FSMContext):
    await message.answer(
        "🔐 <b>Секретная зона</b>\n\n"
        "Введите секретное слово или фразу:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 В меню")]],
            resize_keyboard=True
        )
    )
    await state.set_state(SecretCode.waiting_text)

@dp.message(SecretCode.waiting_text)
async def secret_check(message: Message, state: FSMContext):
    if message.text == "🏠 В меню":
        await state.clear()
        await message.answer("🏠 Главное меню", reply_markup=menu_kb(message.from_user.id == ADMIN_ID))
        return
    
    # Ищем ответ в базе (регистронезависимый поиск)
    cur.execute(
        "SELECT response FROM secret_responses WHERE LOWER(trigger) = LOWER(?)",
        (message.text.strip(),)
    )
    result = cur.fetchone()
    
    if result:
        await message.answer(
            f"✨ <b>Секретный ответ:</b>\n\n{result[0]}",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Неверное секретное слово")
    
    # Остаёмся в режиме ожидания
    await message.answer(
        "Попробуйте ещё или вернитесь в меню:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 В меню")]],
            resize_keyboard=True
        )
    )

# ================= АДМИН: УПРАВЛЕНИЕ СЕКРЕТНЫМИ ОТВЕТАМИ =================
@dp.message(F.text == "🔐 Секретные ответы")
async def admin_secrets_menu(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    cur.execute("SELECT id, trigger, response FROM secret_responses ORDER BY created_at DESC")
    secrets = cur.fetchall()
    
    text = "🔐 <b>Секретные ответы:</b>\n\n"
    
    if secrets:
        for sid, trigger, response in secrets:
            preview = response[:50] + "..." if len(response) > 50 else response
            text += f"🔑 <code>{trigger}</code>\n"
            text += f"   💬 {preview}\n"
            text += f"   🆔 ID: {sid}\n\n"
    else:
        text += "📭 Секретных ответов пока нет\n\n"
    
    text += "Выберите действие:"
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить секретный ответ")],
            [KeyboardButton(text="🗑 Удалить секретный ответ")],
            [KeyboardButton(text="🛠 Админ-панель")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.message(F.text == "➕ Добавить секретный ответ")
async def admin_add_secret_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer(
        "🔑 <b>Добавление секретного ответа</b>\n\n"
        "Введите секретное слово или фразу (триггер):",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🛠 Админ-панель")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AddSecret.trigger)

@dp.message(AddSecret.trigger)
async def admin_add_secret_trigger(message: Message, state: FSMContext):
    if message.text == "🛠 Админ-панель":
        await state.clear()
        await message.answer("🛠 Админ-панель", reply_markup=admin_kb())
        return
    
    trigger = message.text.strip()
    
    # Проверяем, не существует ли уже
    cur.execute("SELECT id FROM secret_responses WHERE LOWER(trigger) = LOWER(?)", (trigger,))
    if cur.fetchone():
        await message.answer("❌ Такой триггер уже существует!")
        return
    
    await state.update_data(trigger=trigger)
    await message.answer(
        f"Триггер: <code>{trigger}</code>\n\n"
        f"Теперь введите ответ, который будет показан пользователю:",
        parse_mode="HTML"
    )
    await state.set_state(AddSecret.response)

@dp.message(AddSecret.response)
async def admin_add_secret_response(message: Message, state: FSMContext):
    if message.text == "🛠 Админ-панель":
        await state.clear()
        await message.answer("🛠 Админ-панель", reply_markup=admin_kb())
        return
    
    data = await state.get_data()
    trigger = data["trigger"]
    response = message.text.strip()
    
    cur.execute(
        "INSERT INTO secret_responses (trigger, response, created_at) VALUES (?, ?, ?)",
        (trigger, response, int(time.time()))
    )
    db.commit()
    
    await message.answer(
        f"✅ <b>Секретный ответ добавлен!</b>\n\n"
        f"🔑 Триггер: <code>{trigger}</code>\n"
        f"💬 Ответ: {response}",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )
    await state.clear()

@dp.message(F.text == "🗑 Удалить секретный ответ")
async def admin_delete_secret(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    cur.execute("SELECT id, trigger FROM secret_responses ORDER BY created_at DESC")
    secrets = cur.fetchall()
    
    if not secrets:
        await message.answer("📭 Секретных ответов пока нет", reply_markup=admin_kb())
        return
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🗑 {trigger}", callback_data=f"delsec:{sid}")]
            for sid, trigger in secrets
        ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="back_admin_secrets")]]
    )
    
    await message.answer(
        "🗑 <b>Удаление секретного ответа</b>\n\n"
        "Выберите, что удалить:",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("delsec:"))
async def admin_delete_secret_confirm(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    
    secret_id = int(call.data.split(":")[1])
    
    cur.execute("SELECT trigger FROM secret_responses WHERE id = ?", (secret_id,))
    result = cur.fetchone()
    
    if result:
        cur.execute("DELETE FROM secret_responses WHERE id = ?", (secret_id,))
        db.commit()
        await call.message.edit_text(
            f"✅ Секретный ответ удалён!\n\n"
            f"🔑 Триггер: <code>{result[0]}</code>",
            parse_mode="HTML"
        )
    else:
        await call.answer("❌ Не найдено")

@dp.callback_query(F.data == "back_admin_secrets")
async def back_admin_secrets(call: CallbackQuery):
    await call.message.delete()
    await call.message.answer("🛠 Админ-панель", reply_markup=admin_kb())
    await call.answer()

# ================= ЗАПУСК =================
async def main():
    print("🚀 BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
