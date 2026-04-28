import asyncio
import logging
import sqlite3
import os
import sys
import time
import json
import datetime
import threading
import uuid
import random
from typing import Final, List, Dict, Optional, Any, Union
from dataclasses import dataclass

# --- EXTERNAL LIBRARIES ---
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import (
    Message, BotCommand, CallbackQuery, DefaultBotProperties, 
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, 
    InlineKeyboardButton, ErrorEvent
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from groq import Groq
from flask import Flask, jsonify
from dotenv import load_dotenv

# Konfiguratsiyani yuklash
load_dotenv()

# ==========================================================================================
# 💎 GLOBAL SYSTEM CONFIGURATION (TITAN KERNEL)
# ==========================================================================================
class TitanKernel:
    VERSION: Final[str] = "v15.0.TITAN.ULTIMATE"
    BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN")
    GROQ_KEY: Final[str] = os.getenv("GROQ_API_KEY")
    ADMINS: Final[List[int]] = [8588645504] # O'z IDingizni qo'shing
    DB_NAME: str = "titan_core_v15.db"
    
    # --- EKOTIZIM PARAMETRLARI ---
    ECONOMY = {
        "START_GOLD": 1000,
        "QUERY_XP": 50,
        "REFERRAL_GOLD": 1500,
        "REFERRAL_XP": 2000,
        "DAILY_BONUS": random.randint(200, 1000),
        "TRANSFER_TAX": 0.05, # 5% komissiya
    }
    
    # --- RANGLAR VA DARAKALAR ---
    RANKS = {
        1: "Novice", 5: "Apprentice", 10: "Warrior", 
        20: "Commander", 50: "Master", 100: "Titan"
    }

    # --- DIZAYN ---
    UI_SEP = "━━━━━━━━━━━━━━━━━━━━━"
    HEADER = "🚀 <b>TITAN OMNI SYSTEM</b>"

# ==========================================================================================
# 🗄️ THREAD-SAFE DATABASE ENGINE (ULTRA RELIABLE)
# ==========================================================================================
class DataEngine:
    """Render muhitida ma'lumotlar bazasi bloklanishini oldini oluvchi dvigatel"""
    def __init__(self):
        self.conn = sqlite3.connect(TitanKernel.DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._build_tables()

    def _build_tables(self):
        with self.lock:
            with self.conn:
                # Foydalanuvchilar jadvali
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        uid INTEGER PRIMARY KEY,
                        name TEXT,
                        username TEXT,
                        gold REAL DEFAULT 1000,
                        xp INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 1,
                        referrals INTEGER DEFAULT 0,
                        referred_by INTEGER,
                        rank TEXT DEFAULT 'Novice',
                        status TEXT DEFAULT 'active',
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # AI Tarixi
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS ai_logs (
                        id TEXT PRIMARY KEY,
                        uid INTEGER,
                        prompt TEXT,
                        response TEXT,
                        timestamp DATETIME
                    )
                """)
                # Tranzaksiyalar
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        tid TEXT PRIMARY KEY,
                        sender_id INTEGER,
                        receiver_id INTEGER,
                        amount REAL,
                        type TEXT,
                        date TIMESTAMP
                    )
                """)
                # Kunlik vazifalar
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS bonus_logs (
                        uid INTEGER PRIMARY KEY,
                        last_date DATE,
                        streak INTEGER DEFAULT 0
                    )
                """)

    def execute(self, sql: str, params: tuple = (), fetch: str = "none"):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(sql, params)
                if fetch == "one": return dict(cursor.fetchone()) if cursor.fetchone() else None
                if fetch == "all": return [dict(r) for r in cursor.fetchall()]
                self.conn.commit()
                return cursor.lastrowid
            except Exception as e:
                logging.error(f"DB_ERROR: {e} | SQL: {sql}")
                return None

db = DataEngine()

# ==========================================================================================
# 🧠 AI NEURAL PROCESSOR (GROQ V3)
# ==========================================================================================
class TitanAI:
    def __init__(self):
        self.client = Groq(api_key=TitanKernel.GROQ_KEY) if TitanKernel.GROQ_KEY else None

    async def generate_response(self, uid: int, prompt: str) -> str:
        if not self.client:
            return "🔴 AI Professor offline rejimda. API kalitni tekshiring."

        try:
            # Tizimga shaxsiyat yuklash
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Siz Titan Omni tizimining bosh AI-miyasiz. O'zbek tilida ilmiy, aniq va do'stona javob berasiz."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                max_tokens=2048,
                temperature=0.6
            )
            ans = response.choices[0].message.content
            
            # Logga yozish
            db.execute("INSERT INTO ai_logs VALUES (?,?,?,?,?)", 
                      (str(uuid.uuid4()), uid, prompt, ans, datetime.datetime.now()))
            return ans
        except Exception as e:
            logging.error(f"AI_CRITICAL: {e}")
            return "⚠️ Neyrotizimda xatolik yuz berdi. Birozdan so'ng urinib ko'ring."

ai = TitanAI()

# ==========================================================================================
# 🎭 STATES & INTERFACE
# ==========================================================================================
class TitanStates(StatesGroup):
    registration = State()
    main_hub = State()
    ai_chat = State()
    transfer_id = State()
    transfer_amount = State()
    admin_broadcast = State()

class TitanUI:
    @staticmethod
    def main_menu(uid: int):
        builder = ReplyKeyboardBuilder()
        builder.row(KeyboardButton(text="🧠 AI TITAN"), KeyboardButton(text="👤 PROFIL"))
        builder.row(KeyboardButton(text="💰 HAMYON"), KeyboardButton(text="🏆 REYTING"))
        builder.row(KeyboardButton(text="🤝 HAMKORLAR"), KeyboardButton(text="🎁 KUNLIK BONUS"))
        builder.row(KeyboardButton(text="⚙️ SOZLAMALAR"))
        
        if uid in TitanKernel.ADMINS:
            builder.row(KeyboardButton(text="👑 ADMIN PANEL"))
        
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def inline_back():
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_menu")]
        ])

# ==========================================================================================
# 🤖 BOT LOGIC & HANDLERS
# ==========================================================================================
bot = Bot(token=TitanKernel.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# --- MIDDLEWARE: USER AUTO-CHECK ---
@dp.message.outer_middleware()
async def user_middleware(handler, event: Message, data: dict):
    if not event.from_user: return await handler(event, data)
    
    uid = event.from_user.id
    user = db.execute("SELECT * FROM users WHERE uid = ?", (uid,), fetch="one")
    
    if not user and not event.text.startswith("/start"):
        await event.answer("⚠️ Tizimdan foydalanish uchun avval /start buyrug'ini bosing.")
        return
    
    return await handler(event, data)

# --- COMMANDS ---
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    uid = message.from_user.id
    user = db.execute("SELECT * FROM users WHERE uid = ?", (uid,), fetch="one")
    
    # Referal tizimi
    ref_id = None
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])

    if not user:
        await state.update_data(ref_id=ref_id)
        await state.set_state(TitanStates.registration)
        return await message.answer(
            f"{TitanKernel.HEADER}\n{TitanKernel.UI_SEP}\n"
            "Xush kelibsiz! Titan ekotizimiga kirish uchun <b>Ismingizni kiriting:</b>"
        )

    await message.answer(f"Xush kelibsiz, <b>{user['name']}</b>!", reply_markup=TitanUI.main_menu(uid))

@dp.message(TitanStates.registration)
async def process_reg(message: Message, state: FSMContext):
    uid = message.from_user.id
    name = message.text
    data = await state.get_data()
    ref_id = data.get("ref_id")
    
    # Foydalanuvchini yaratish
    db.execute(
        "INSERT INTO users (uid, name, username, referred_by) VALUES (?,?,?,?)",
        (uid, name, message.from_user.username, ref_id)
    )
    
    if ref_id and ref_id != uid:
        db.execute("UPDATE users SET gold = gold + ?, xp = xp + ?, referrals = referrals + 1 WHERE uid = ?", 
                  (TitanKernel.ECONOMY["REFERRAL_GOLD"], TitanKernel.ECONOMY["REFERRAL_XP"], ref_id))
        try:
            await bot.send_message(ref_id, f"🎊 <b>Yangi hamkor!</b>\nSizga {TitanKernel.ECONOMY['REFERRAL_GOLD']} oltin berildi.")
        except: pass

    await message.answer("✅ Ro'yxatdan muvaffaqiyatli o'tdingiz!", reply_markup=TitanUI.main_menu(uid))
    await state.clear()

# --- AI INTERACTION ---
@dp.message(F.text == "🧠 AI TITAN")
async def ai_start(message: Message, state: FSMContext):
    await state.set_state(TitanStates.ai_chat)
    await message.answer("🧠 <b>Titan AI Professor sizni eshitadi.</b>\nSavolingizni yo'llang (Chiqish uchun: /stop):")

@dp.message(TitanStates.ai_chat)
async def ai_process(message: Message, state: FSMContext):
    if message.text == "/stop":
        await state.clear()
        return await message.answer("AI to'xtatildi.", reply_markup=TitanUI.main_menu(message.from_user.id))

    loading = await message.answer("⚡️ <i>Titan hisoblamoqda...</i>")
    response = await ai.generate_response(message.from_user.id, message.text)
    
    # Mukofotlash
    db.execute("UPDATE users SET xp = xp + ? WHERE uid = ?", (TitanKernel.ECONOMY["QUERY_XP"], message.from_user.id))
    
    try:
        await loading.edit_text(response)
    except:
        await message.answer(response)

# --- PROFILE & ECONOMY ---
@dp.message(F.text == "👤 PROFIL")
async def cmd_profile(message: Message):
    u = db.execute("SELECT * FROM users WHERE uid = ?", (message.from_user.id,), fetch="one")
    text = (
        f"👤 <b>TITAN USER PROFILE</b>\n{TitanKernel.UI_SEP}\n"
        f"ID: <code>{u['uid']}</code>\n"
        f"Ism: <b>{u['name']}</b>\n"
        f"Daraja: <b>{u['level']} [{u['rank']}]</b>\n"
        f"Oltin: <b>{u['gold']:.2f} 🪙</b>\n"
        f"XP: <b>{u['xp']}</b>\n"
        f"Hamkorlar: <b>{u['referrals']} ta</b>\n"
        f"{TitanKernel.UI_SEP}"
    )
    await message.answer(text)

@dp.message(F.text == "🎁 KUNLIK BONUS")
async def cmd_bonus(message: Message):
    uid = message.from_user.id
    today = datetime.date.today()
    log = db.execute("SELECT * FROM bonus_logs WHERE uid = ?", (uid,), fetch="one")
    
    if log and log['last_date'] == str(today):
        return await message.answer("❌ Bugun bonus olgansiz. Ertaga qaytib keling!")
    
    amount = TitanKernel.ECONOMY["DAILY_BONUS"]
    if not log:
        db.execute("INSERT INTO bonus_logs (uid, last_date, streak) VALUES (?,?,?)", (uid, today, 1))
    else:
        db.execute("UPDATE bonus_logs SET last_date = ?, streak = streak + 1 WHERE uid = ?", (today, uid))
    
    db.execute("UPDATE users SET gold = gold + ? WHERE uid = ?", (amount, uid))
    await message.answer(f"🎁 <b>Tabriklaymiz!</b>\nSizga bugun {amount} oltin berildi!")

# ==========================================================================================
# 🌐 WEB SERVER & RENDER KEEP-ALIVE
# ==========================================================================================
app = Flask(__name__)

@app.route('/')
def status():
    return jsonify({
        "status": "online",
        "system": "TITAN_OMNI",
        "version": TitanKernel.VERSION,
        "active_users": len(db.execute("SELECT uid FROM users", fetch="all"))
    })

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==========================================================================================
# 🚀 SYSTEM BOOTSTRAP
# ==========================================================================================
async def main():
    # Render uchun Flaskni alohida threadga o'tkazish
    threading.Thread(target=run_flask, daemon=True).start()
    
    logging.basicConfig(level=logging.INFO)
    
    # Bot buyruqlarini sozlash
    await bot.set_my_commands([
        BotCommand(command="start", description="Tizimni ishga tushirish"),
        BotCommand(command="help", description="Yordam markazi"),
        BotCommand(command="profile", description="Profilni ko'rish")
    ])
    
    logging.info(f"TITAN CORE {TitanKernel.VERSION} IS RUNNING...")
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logging.critical(f"FATAL_ERROR: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("TITAN ENGINE OFFLINE.")
