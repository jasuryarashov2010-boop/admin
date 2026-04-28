import asyncio
import logging
import sqlite3
import os
import json
import datetime
import threading
from groq import AsyncGroq
from typing import Final, List, Dict, Optional, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import (
    Message, BotCommand, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from groq import Groq
from flask import Flask, jsonify
from dotenv import load_dotenv

# Kalitlarni xavfsiz yuklash
load_dotenv()

# ==========================================================================================
# 💎 TITAN OMNI KERNEL V17 (PREMIUM PLUS EDITION)
# ==========================================================================================
class Config:
    VERSION: Final[str] = "v17.0.PREMIUM.PLUS"
    BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN")
    GROQ_KEY: Final[str] = os.getenv("GROQ_API_KEY")
    ADMIN_ID: Final[int] = int(os.getenv("ADMIN_ID", 8588645504))
    DB_NAME: str = "titan_academy_v17.db"
    
    START_TIME = datetime.datetime.now()
    UI_DIV = "<b>" + "✦" * 15 + "</b>"
    LOGO = "🎓 <b>TITAN ACADEMY SYSTEM</b>"

# ==========================================================================================
# 🗄️ MA'LUMOTLAR BAZASI ENGINE (BLOCK-PROOF)
# ==========================================================================================
class DataEngine:
    def __init__(self):
        self.conn = sqlite3.connect(Config.DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self.lock:
            with self.conn:
                # Foydalanuvchilar
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        uid INTEGER PRIMARY KEY,
                        name TEXT,
                        username TEXT,
                        total_tests INTEGER DEFAULT 0,
                        avg_score REAL DEFAULT 0.0,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Testlar
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS tests (
                        test_code TEXT PRIMARY KEY,
                        title TEXT,
                        answers TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Natijalar
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        uid INTEGER,
                        test_code TEXT,
                        score INTEGER,
                        total INTEGER,
                        percentage REAL,
                        wrong_answers TEXT,
                        solved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

    def query(self, sql: str, params: tuple = (), fetch: str = "none"):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(sql, params)
                if fetch == "one":
                    res = cursor.fetchone()
                    return dict(res) if res else None
                if fetch == "all":
                    return [dict(r) for r in cursor.fetchall()]
                self.conn.commit()
                return cursor.lastrowid
            except Exception as e:
                logging.error(f"DATABASE_ERROR: {e}")
                return None

db = DataEngine()
# ==========================================================================================
# 🧠 AI NEYRO-TIZIM (ADVANCED PRO EDITION)
# ==========================================================================================
class NeuralCore:
    def __init__(self):
        # Konfiguratsiya: Render muhitidan xavfsiz yuklash
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = "llama-3.3-70b-versatile"
        self.temperature = 0.5  # O'quv tahlillari uchun aniqlik darajasi
        self.max_retries = 3    # API xatolarida qayta urinishlar soni
        
        # Asinxron Groq mijozini yaratish
        self.client = AsyncGroq(api_key=self.api_key) if self.api_key else None
        
        if not self.client:
            logging.error("❌ CRITICAL: GROQ_API_KEY topilmadi! AI tahlil o'chirilgan.")

    async def _execute_with_retry(self, messages: List[Dict[str, str]]) -> str:
        """
        API so'rovlarini xavfsiz bajarish va xatolik bo'lsa qayta urinish mexanizmi.
        Bu botni kutilmagan to'xtashlardan asraydi.
        """
        for attempt in range(self.max_retries):
            try:
                # Asinxron so'rov (Botni bloklamaydi)
                completion = await self.client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=3500, # Uzun tahlillar uchun yetarli joy
                    top_p=0.9,
                )
                
                # Statistika uchun (Loglarda ko'rinadi)
                tokens = completion.usage.total_tokens
                logging.info(f"🤖 AI Javobi muvaffaqiyatli: {tokens} token sarflandi.")
                
                return completion.choices[0].message.content

            except Exception as e:
                error_msg = str(e).lower()
                logging.warning(f"⚠️ AI urinish {attempt+1} xatosi: {error_msg}")
                
                # Agar limit tugagan bo'lsa yoki server xatosi bo'lsa, biroz kutamiz
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    await asyncio.sleep(wait_time)
                else:
                    if "rate_limit" in error_msg:
                        return "🔴 Kechirasiz, AI hozirda juda ko'p so'rov qabul qilmoqda. 1 daqiqadan so'ng urinib ko'ring."
                    return f"⚠️ Tizimda texnik muammo yuz berdi. (Xato turi: {type(e).__name__})"

    async def ask_ai(self, prompt: str, context: str = "Siz Titan Academy platformasining aqlli va mehribon AI ustozisiz.") -> str:
        """Ixtiyoriy savollarga javob berish (General Purpose)"""
        if not self.client:
            return "🔴 AI xizmati faollashtirilmagan."

        messages = [
            {"role": "system", "content": context},
            {"role": "user", "content": prompt}
        ]
        return await self._execute_with_retry(messages)

    async def analyze_mistakes(self, test_title: str, wrong_answers: dict) -> str:
        """
        O'quvchining xatolarini chuqur pedagogik tahlil qilish.
        """
        if not wrong_answers:
            return "🌟 <b>Tabriklayman!</b> Siz barcha savollarga to'g'ri javob berdingiz. Bilimingiz a'lo darajada!"

        # Xatolarni chiroyli va tartibli ko'rinishga keltirish
        wrongs_formatted = ""
        for q_num, data in wrong_answers.items():
            wrongs_formatted += (
                f"📍 <b>Savol №{q_num}</b>\n"
                f"❌ Sizning tanlovingiz: <i>{data['user']}</i>\n"
                f"✅ To'g'ri javob: <b>{data['correct']}</b>\n"
                f"{'—' * 10}\n"
            )

        # AI uchun maxsus Master-Prompt
        analysis_prompt = (
            f"O'quvchi '{test_title}' testini topshirdi va quyidagi xatolarni qildi:\n\n"
            f"{wrongs_formatted}\n"
            "Iltimos, ushbu xatolarning har birini professional pedagog sifatida tahlil qiling. "
            "To'g'ri javob nega aynan shu ekanligini mantiqiy, ilmiy va tushunarli tushuntiring. "
            "Javob oxirida o'quvchiga motivatsiya beruvchi so'zlar yozing."
        )

        system_instruction = (
            "Siz o'zbek tilida so'zlashuvchi, tajribali va juda sabrli ustozsiz. "
            "O'quvchini xatosi uchun urushmang, aksincha xatodan bilim olishga yo'naltiring. "
            "Javobingizda HTML teglardan (<b>, <i>) foydalanib, chiroyli formatlang."
        )

        return await self.ask_ai(analysis_prompt, system_instruction)

    async def generate_study_plan(self, results: List[Dict[str, Any]]) -> str:
        """O'quvchining bir nechta test natijalariga qarab individual reja tuzish"""
        prompt = f"O'quvchining oxirgi natijalari: {results}. Uning kuchsiz tomonlarini aniqlang va o'qish rejasini tuzing."
        return await self.ask_ai(prompt, "Siz strategik ta'lim bo'yicha mutaxassisiz.")

# Global initsializatsiya
ai_engine = NeuralCore()

# ==========================================================================================
# 🎮 HOLATLAR (FSM)
# ==========================================================================================
class UserStates(StatesGroup):
    ai_waiting = State()
    test_code_input = State()
    test_answers_input = State()
    contact_admin = State()
    admin_replying = State()
    
class AdminStates(StatesGroup):
    add_test_code = State()
    add_test_title = State()
    add_test_answers = State()
    delete_test = State()
    broadcast_msg = State()
    view_test_stats = State()

# ==========================================================================================
# 🎨 INTERFEYS VA DIZAYN
# ==========================================================================================
class UI:
    BTN_BACK = "🔙 Orqaga"

    @staticmethod
    def main_menu(uid: int):
        builder = ReplyKeyboardBuilder()
        builder.row(KeyboardButton(text="📝 Testlar ro'yxati"), KeyboardButton(text="🎯 Test tekshirish"))
        builder.row(KeyboardButton(text="🧠 AI Ustoz"), KeyboardButton(text="📊 Natijalarim"))
        builder.row(KeyboardButton(text="👤 Profilim"), KeyboardButton(text="📞 Bog'lanish"))
        if uid == Config.ADMIN_ID:
            builder.row(KeyboardButton(text="👑 ADMIN PANEL"))
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def back_menu():
        builder = ReplyKeyboardBuilder()
        builder.button(text=UI.BTN_BACK)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def admin_menu():
        builder = ReplyKeyboardBuilder()
        builder.row(KeyboardButton(text="➕ Test qo'shish"), KeyboardButton(text="🗑 Testni o'chirish"))
        builder.row(KeyboardButton(text="📢 Xabar berish"), KeyboardButton(text="📈 Batafsil statistika"))
        builder.row(KeyboardButton(text=UI.BTN_BACK))
        return builder.as_markup(resize_keyboard=True)

# ==========================================================================================
# 🚀 BOT LOGIKASI
# ==========================================================================================
bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# --- ORQAGA QAYTISH TUGMASI UCHUN UMUMIY HANDLER ---
@dp.message(F.text == UI.BTN_BACK)
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if message.chat.id == Config.ADMIN_ID and message.text == "👑 ADMIN PANEL":
        await message.answer("Bosh sahifaga qaytdingiz.", reply_markup=UI.main_menu(uid))
    else:
        await message.answer(f"🏠 Bosh menyudasiz.\n{Config.UI_DIV}", reply_markup=UI.main_menu(uid))

# --- START COMMAND ---
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    user = db.query("SELECT * FROM users WHERE uid = ?", (uid,), fetch="one")
    
    if not user:
        db.query("INSERT INTO users (uid, name, username) VALUES (?,?,?)",
                 (uid, message.from_user.full_name, message.from_user.username))
    
    text = (
        f"{Config.LOGO}\n{Config.UI_DIV}\n"
        f"Assalomu alaykum, <b>{message.from_user.full_name}</b>! 🌟\n\n"
        f"<i>Premium test ishlash va AI tahlil tizimiga xush kelibsiz. Quyidagi menyudan kerakli bo'limni tanlang:</i>"
    )
    await message.answer(text, reply_markup=UI.main_menu(uid))

# --- 📝 TESTLAR RO'YXATI ---
@dp.message(F.text == "📝 Testlar ro'yxati")
async def list_tests(message: Message):
    tests = db.query("SELECT * FROM tests ORDER BY created_at DESC LIMIT 20", fetch="all")
    if not tests:
        return await message.answer("Tizimda hozircha testlar mavjud emas.")
    
    text = f"📋 <b>Mavjud testlar ro'yxati:</b>\n{Config.UI_DIV}\n\n"
    for t in tests:
        text += f"🔖 <b>Kod:</b> <code>{t['test_code']}</code>\n"
        text += f"📌 <b>Mavzu:</b> {t['title']}\n"
        text += f"📏 <b>Savollar soni:</b> {len(t['answers'])}\n\n"
    
    await message.answer(text)

# --- 🎯 TEST TEKSHIRISH ---
@dp.message(F.text == "🎯 Test tekshirish")
async def init_test_check(message: Message, state: FSMContext):
    await state.set_state(UserStates.test_code_input)
    await message.answer("🎯 Iltimos, ishlagan testingizning <b>KODINI</b> kiriting:", reply_markup=UI.back_menu())

@dp.message(StateFilter(UserStates.test_code_input))
async def get_test_code(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    code = message.text.strip().upper()
    test = db.query("SELECT * FROM tests WHERE test_code = ?", (code,), fetch="one")
    
    if not test:
        return await message.answer("❌ Bunday kodli test topilmadi. Qaytadan urinib ko'ring:")
    
    # Oldin ishlaganligini tekshirish
    already_solved = db.query("SELECT id FROM results WHERE uid = ? AND test_code = ?", (message.from_user.id, code), fetch="one")
    if already_solved:
        await state.clear()
        return await message.answer("⚠️ <b>Siz bu testni avval ishlangansiz!</b>\nNatijalarni '📊 Natijalarim' bo'limidan ko'rishingiz mumkin.", reply_markup=UI.main_menu(message.from_user.id))
    
    await state.update_data(test_code=code, correct_answers=test['answers'])
    await state.set_state(UserStates.test_answers_input)
    await message.answer(f"✅ Test topildi: <b>{test['title']}</b>\n\n📝 Endi o'z javoblaringizni yuboring (Masalan: <code>abcdabcd...</code>):")

@dp.message(StateFilter(UserStates.test_answers_input))
async def check_test_answers(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    data = await state.get_data()
    correct_answers = data['correct_answers'].lower()
    user_answers = message.text.strip().lower().replace(" ", "")
    
    if len(correct_answers) != len(user_answers):
        return await message.answer(f"⚠️ <b>Javoblar soni mos tushmadi!</b>\nTestda {len(correct_answers)} ta savol bor, siz {len(user_answers)} ta javob yubordingiz. Qaytadan kiriting:")
    
    score = 0
    wrong_answers = {}
    for i, (correct, user) in enumerate(zip(correct_answers, user_answers), 1):
        if correct == user:
            score += 1
        else:
            wrong_answers[str(i)] = {"user": user, "correct": correct}
            
    total = len(correct_answers)
    percentage = round((score / total) * 100, 1)
    wrong_json = json.dumps(wrong_answers)
    
    # Natijani saqlash
    db.query("INSERT INTO results (uid, test_code, score, total, percentage, wrong_answers) VALUES (?,?,?,?,?,?)",
             (message.from_user.id, data['test_code'], score, total, percentage, wrong_json))
    
    # Foydalanuvchi statistikasini yangilash
    stats = db.query("SELECT AVG(percentage) as avg_pct, COUNT(id) as total_tests FROM results WHERE uid = ?", (message.from_user.id,), fetch="one")
    db.query("UPDATE users SET total_tests = ?, avg_score = ? WHERE uid = ?", 
             (stats['total_tests'], stats['avg_pct'], message.from_user.id))
    
    result_text = (
        f"🏆 <b>TEST NATIJASI</b>\n{Config.UI_DIV}\n"
        f"🔖 <b>Test kodi:</b> {data['test_code']}\n"
        f"✅ <b>To'g'ri javoblar:</b> {score} ta\n"
        f"❌ <b>Xato javoblar:</b> {total - score} ta\n"
        f"📊 <b>Ko'rsatkich:</b> {percentage}%\n\n"
        f"<i>Batafsil xatolarni '📊 Natijalarim' bo'limida ko'rishingiz va AI orqali tahlil qilishingiz mumkin.</i>"
    )
    
    await state.clear()
    await message.answer(result_text, reply_markup=UI.main_menu(message.from_user.id))

# --- 🧠 AI USTOZ ---
@dp.message(F.text == "🧠 AI Ustoz")
async def ai_teacher_mode(message: Message, state: FSMContext):
    await state.set_state(UserStates.ai_waiting)
    text = "🧠 <b>AI Ustoz xizmatingizda!</b>\n\nIstagan faningizdan yoki testdagi tushunmagan savolingiz bo'yicha menga yozing:"
    await message.answer(text, reply_markup=UI.back_menu())

@dp.message(StateFilter(UserStates.ai_waiting))
async def process_ai_question(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    msg = await message.answer("🔄 <i>Savolingiz tahlil qilinmoqda, kuting...</i>")
    response = await ai_engine.ask_ai(message.text)
    await msg.edit_text(response)

# --- 📊 NATIJALARIM VA AI TAHLIL ---
@dp.message(F.text == "📊 Natijalarim")
async def my_results(message: Message):
    results = db.query("""
        SELECT r.*, t.title FROM results r 
        JOIN tests t ON r.test_code = t.test_code 
        WHERE r.uid = ? ORDER BY r.solved_at DESC LIMIT 5
    """, (message.from_user.id,), fetch="all")
    
    if not results:
        return await message.answer("Siz hali birorta ham test ishlamagansiz.")
    
    builder = InlineKeyboardBuilder()
    text = f"📊 <b>Sizning so'nggi natijalaringiz:</b>\n{Config.UI_DIV}\n\n"
    
    for r in results:
        text += f"🔖 <b>{r['title']}</b> (Kod: {r['test_code']})\n"
        text += f"Ko'rsatkich: {r['score']}/{r['total']} ({r['percentage']}%)\n\n"
        builder.row(InlineKeyboardButton(text=f"🔍 Tahlil: {r['test_code']}", callback_data=f"analyze_{r['id']}"))
    
    await message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("analyze_"))
async def ai_analysis_callback(call: CallbackQuery):
    res_id = call.data.split("_")[1]
    result = db.query("""
        SELECT r.wrong_answers, t.title FROM results r 
        JOIN tests t ON r.test_code = t.test_code 
        WHERE r.id = ?
    """, (res_id,), fetch="one")
    
    if not result:
        return await call.answer("Natija topilmadi.", show_alert=True)
    
    wrong_answers = json.loads(result['wrong_answers'])
    if not wrong_answers:
        return await call.answer("Qoyil! Bu testda umuman xato qilmadingiz.", show_alert=True)
    
    await call.message.edit_text("🔄 <i>AI Ustoz xatolaringizni tahlil qilmoqda... Bir oz kuting.</i>")
    
    analysis = await ai_engine.analyze_mistakes(result['title'], wrong_answers)
    final_text = f"🧠 <b>AI XATOLAR TAHLILI</b>\n{Config.UI_DIV}\n{analysis}"
    
    await call.message.edit_text(final_text)

# --- 👤 PROFILIM ---
@dp.message(F.text == "👤 Profilim")
async def profile_handler(message: Message):
    u = db.query("SELECT * FROM users WHERE uid = ?", (message.from_user.id,), fetch="one")
    if not u: return
    
    text = (
        f"👤 <b>PROFIL MALUMOTLARI</b>\n{Config.UI_DIV}\n"
        f"🆔 <b>ID:</b> <code>{u['uid']}</code>\n"
        f"👤 <b>Ism:</b> {u['name']}\n"
        f"📝 <b>Ishlangan testlar:</b> {u['total_tests']} ta\n"
        f"📈 <b>O'rtacha o'zlashtirish:</b> {round(u['avg_score'], 1)}%\n"
        f"📅 <b>Ro'yxatdan o'tgan:</b> {u['joined_at'][:10]}\n"
        f"{Config.UI_DIV}"
    )
    await message.answer(text)

# --- 📞 BOG'LANISH VA ADMIN JAVOBI ---
@dp.message(F.text == "📞 Bog'lanish")
async def contact_admin(message: Message, state: FSMContext):
    await state.set_state(UserStates.contact_admin)
    await message.answer("✍️ Adminga o'z xabar, taklif yoki shikoyatingizni yozib qoldiring:", reply_markup=UI.back_menu())

@dp.message(StateFilter(UserStates.contact_admin))
async def send_to_admin(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Javob berish", callback_data=f"reply_{message.from_user.id}"))
    
    admin_text = f"📩 <b>Yangi xabar!</b>\nKimdan: {message.from_user.full_name} (@{message.from_user.username})\nID: <code>{message.from_user.id}</code>\n\n📝 Xabar:\n{message.text}"
    
    try:
        await bot.send_message(Config.ADMIN_ID, admin_text, reply_markup=builder.as_markup())
        await message.answer("✅ Xabaringiz adminga yetkazildi. Tez orada javob olasiz.", reply_markup=UI.main_menu(message.from_user.id))
    except:
        await message.answer("❌ Xatolik yuz berdi. Admin botni bloklagan bo'lishi mumkin.")
    await state.clear()

@dp.callback_query(F.data.startswith("reply_"))
async def admin_reply_callback(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != Config.ADMIN_ID: return
    user_id = call.data.split("_")[1]
    await state.update_data(reply_to=user_id)
    await state.set_state(UserStates.admin_replying)
    await call.message.answer(f"✏️ {user_id} ID egasiga javobingizni yozing:", reply_markup=UI.back_menu())
    await call.answer()

@dp.message(StateFilter(UserStates.admin_replying))
async def send_reply_to_user(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    data = await state.get_data()
    user_id = data.get('reply_to')
    
    try:
        await bot.send_message(user_id, f"🔔 <b>Admindan javob keldi:</b>\n\n{message.text}")
        await message.answer("✅ Javobingiz yuborildi.", reply_markup=UI.admin_menu())
    except:
        await message.answer("❌ Foydalanuvchi botni bloklagan.", reply_markup=UI.admin_menu())
    await state.clear()


# ==========================================================================================
# 👑 ADMIN PANEL FUNKSIYALARI
# ==========================================================================================
@dp.message(F.text == "👑 ADMIN PANEL")
async def open_admin_panel(message: Message):
    if message.from_user.id != Config.ADMIN_ID: return
    await message.answer("👑 <b>Admin panelga xush kelibsiz!</b>", reply_markup=UI.admin_menu())

# --- ➕ TEST QO'SHISH ---
@dp.message(F.text == "➕ Test qo'shish")
async def add_test_start(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(AdminStates.add_test_code)
    await message.answer("Yangi test uchun noyob KOD kiriting (Masalan: BIO101):", reply_markup=UI.back_menu())

@dp.message(StateFilter(AdminStates.add_test_code))
async def add_test_code(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    code = message.text.strip().upper()
    check = db.query("SELECT test_code FROM tests WHERE test_code = ?", (code,), fetch="one")
    if check: return await message.answer("❌ Bu kod band! Boshqa kod kiriting:")
    
    await state.update_data(test_code=code)
    await state.set_state(AdminStates.add_test_title)
    await message.answer("📝 Test sarlavhasini kiriting (Masalan: Biologiya 10-sinf chorak):")

@dp.message(StateFilter(AdminStates.add_test_title))
async def add_test_title(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    await state.update_data(title=message.text)
    await state.set_state(AdminStates.add_test_answers)
    await message.answer("🔑 Testning to'g'ri javoblarini uzluksiz ketma-ketlikda kiriting (Masalan: abcdabcdabcd):")

@dp.message(StateFilter(AdminStates.add_test_answers))
async def add_test_answers(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    data = await state.get_data()
    answers = message.text.strip().lower().replace(" ", "")
    
    db.query("INSERT INTO tests (test_code, title, answers) VALUES (?,?,?)",
             (data['test_code'], data['title'], answers))
    
    await state.clear()
    await message.answer(f"✅ <b>Test muvaffaqiyatli qo'shildi!</b>\nKod: {data['test_code']}\nSavollar: {len(answers)} ta", reply_markup=UI.admin_menu())

# --- 🗑 TESTNI O'CHIRISH ---
@dp.message(F.text == "🗑 Testni o'chirish")
async def delete_test_start(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(AdminStates.delete_test)
    await message.answer("🗑 O'chiriladigan test KODINI kiriting:", reply_markup=UI.back_menu())

@dp.message(StateFilter(AdminStates.delete_test))
async def delete_test_process(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    code = message.text.strip().upper()
    test = db.query("SELECT test_code FROM tests WHERE test_code = ?", (code,), fetch="one")
    if not test: return await message.answer("❌ Bunday test topilmadi.")
    
    db.query("DELETE FROM tests WHERE test_code = ?", (code,))
    db.query("DELETE FROM results WHERE test_code = ?", (code,)) # Bog'liq natijalarni ham o'chirish
    
    await state.clear()
    await message.answer(f"✅ <b>{code}</b> kodi ostidagi test barcha natijalari bilan birga o'chirildi.", reply_markup=UI.admin_menu())

# --- 📢 XABAR BERISH ---
@dp.message(F.text == "📢 Xabar berish")
async def broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(AdminStates.broadcast_msg)
    await message.answer("Hamma foydalanuvchilarga yuboriladigan xabarni kiriting:", reply_markup=UI.back_menu())

@dp.message(StateFilter(AdminStates.broadcast_msg))
async def broadcast_process(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    users = db.query("SELECT uid FROM users", fetch="all")
    success, fail = 0, 0
    
    await message.answer("🔄 Xabar yuborilmoqda, kuting...")
    
    for u in users:
        try:
            await bot.send_message(u['uid'], message.text)
            success += 1
            await asyncio.sleep(0.05) # Spam limitga tushmaslik uchun
        except:
            fail += 1
            
    await state.clear()
    await message.answer(f"✅ <b>Tarqatish yakunlandi.</b>\nYuborildi: {success} ta\nYetib bormadi: {fail} ta", reply_markup=UI.admin_menu())

# --- 📈 BATAFSIL STATISTIKA ---
@dp.message(F.text == "📈 Batafsil statistika")
async def stats_start(message: Message, state: FSMContext):
    if message.from_user.id != Config.ADMIN_ID: return
    await state.set_state(AdminStates.view_test_stats)
    await message.answer("Statistikasini ko'rmoqchi bo'lgan test KODINI kiriting:", reply_markup=UI.back_menu())

@dp.message(StateFilter(AdminStates.view_test_stats))
async def stats_process(message: Message, state: FSMContext):
    if message.text == UI.BTN_BACK: return await go_back(message, state)
    
    code = message.text.strip().upper()
    results = db.query("""
        SELECT r.*, u.name, u.username FROM results r 
        JOIN users u ON r.uid = u.uid 
        WHERE r.test_code = ? ORDER BY r.score DESC
    """, (code,), fetch="all")
    
    if not results:
        return await message.answer("Bu testni hali hech kim ishlamagan.")
    
    avg_score = sum([r['percentage'] for r in results]) / len(results)
    
    text = f"📈 <b>{code} testi statistikasi:</b>\n{Config.UI_DIV}\n"
    text += f"👥 <b>Qatnashchilar:</b> {len(results)} ta\n"
    text += f"📊 <b>O'rtacha foiz:</b> {round(avg_score, 1)}%\n\n"
    text += "🏆 <b>TOP Natijalar:</b>\n"
    
    for i, r in enumerate(results[:15], 1):
        uname = f"(@{r['username']})" if r['username'] else ""
        text += f"{i}. {r['name']} {uname} - {r['score']}/{r['total']} ({r['percentage']}%)\n"
    
    await state.clear()
    await message.answer(text, reply_markup=UI.admin_menu())


# ==========================================================================================
# 🌐 RENDER KEEP-ALIVE SERVER (WEBSERVER)
# ==========================================================================================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    uptime = str(datetime.datetime.now() - Config.START_TIME).split('.')[0]
    return jsonify({
        "system": "Titan Academy Premium",
        "status": "Online 24/7",
        "uptime": uptime,
        "features": ["Tests", "AI Analysis", "Admin Panel"]
    })

def start_server():
    port = int(os.environ.get("PORT", 8080))
    # Render xato bermasligi uchun 0.0.0.0 muhim
    web_app.run(host="0.0.0.0", port=port, use_reloader=False)

# ==========================================================================================
# 🚀 ASOSIY ISHGA TUSHIRISH (EXECUTION)
# ==========================================================================================
async def main():
    # Flask serverni alohida thread'da ishga tushirish (Render talabi)
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Bot komandalarini menyuga qadash
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni qayta ishga tushirish")
    ])
    
    logging.info(f"--- TITAN ACADEMY {Config.VERSION} SYSTEM ONLINE ---")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Tizim muvaffaqiyatli to'xtatildi.")
