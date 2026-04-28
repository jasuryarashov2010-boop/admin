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
import hashlib
from typing import Final, List, Dict, Optional, Any, Union, Tuple
from dataclasses import dataclass

# --- PROFESSIONAL ASYNC STACK ---
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import (
    Message, BotCommand, BufferedInputFile, CallbackQuery, 
    DefaultBotProperties, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, InputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from groq import Groq
from flask import Flask, jsonify
from dotenv import load_dotenv

# Konfiguratsiyani yuklash
load_dotenv()

# ==========================================================================================
# 🌌 INFINITY KERNEL (SISTEMA KONFIGURATSIYASI)
# ==========================================================================================
class InfinityKernel:
    VERSION: Final[str] = "v14.0.INFINITY.GOLD"
    TOKEN: Final[str] = os.getenv("BOT_TOKEN")
    GROQ_KEY: Final[str] = os.getenv("GROQ_API_KEY")
    ADMINS: Final[List[int]] = [8588645504]  # SIZNING ID
    DB_NAME: str = "logos_infinity.db"
    
    # --- EKONOMIKA PARAMETRLARI ---
    ECONOMY = {
        "START_GOLD": 500,
        "START_ENERGY": 100,
        "AI_COST": 5,           # Har bir savol uchun energiya
        "AI_REWARD_XP": 50,     # Har bir savol uchun tajriba
        "REF_REWARD_GOLD": 1000,
        "DAILY_BONUS_MIN": 100,
        "DAILY_BONUS_MAX": 500
    }
    
    # --- DIZAYN ELEMENTLARI ---
    THEME = {
        "HEADER": "<b>✨ LOGOS INFINITY TIZIMI</b>",
        "DIVIDER": "<b>━━━━━━━━━━━━━━━━━━━━━</b>",
        "SUCCESS": "🟢",
        "WARNING": "🟡",
        "ERROR": "🔴",
        "AI": "🤖",
        "GOLD": "💰",
        "XP": "⚡️",
        "ENERGY": "🔋"
    }

# ==========================================================================================
# 🗄️ TITAN DATABASE CONTROLLER (RENDER-OPTIMIZED)
# ==========================================================================================
class TitanDB:
    """Thread-safe asinxron ishlashga moslashgan ma'lumotlar bazasi boshqaruvchisi"""
    def __init__(self):
        self.conn = sqlite3.connect(InfinityKernel.DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._infrastructure_init()

    def _infrastructure_init(self):
        with self.lock:
            with self.conn:
                # FOYDALANUVCHILAR
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        uid INTEGER PRIMARY KEY,
                        fullname TEXT,
                        username TEXT,
                        gold REAL DEFAULT 500.0,
                        xp INTEGER DEFAULT 0,
                        energy INTEGER DEFAULT 100,
                        level INTEGER DEFAULT 1,
                        prestige INTEGER DEFAULT 0,
                        referred_by INTEGER,
                        last_active TIMESTAMP,
                        status TEXT DEFAULT 'User',
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # LOGLAR VA TRANZAKSIYALAR
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        uid INTEGER,
                        amount REAL,
                        type TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # KUNLIK BONUSLAR
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS bonus_logs (
                        uid INTEGER PRIMARY KEY,
                        last_claim DATE
                    )
                """)

    def execute(self, query: str, params: tuple = (), fetch: str = "none"):
        with self.lock:
            try:
                cursor = self.conn.cursor()
                cursor.execute(query, params)
                if fetch == "one": return dict(cursor.fetchone()) if cursor.description else None
                if fetch == "all": return [dict(r) for r in cursor.fetchall()]
                self.conn.commit()
                return cursor.lastrowid
            except Exception as e:
                logging.error(f"SQL_FAIL: {e} | Query: {query}")
                return None

db = TitanDB()

# ==========================================================================================
# 🧠 NEURAL CORE v2.0
# ==========================================================================================
class NeuralCore:
    def __init__(self):
        self.client = Groq(api_key=InfinityKernel.GROQ_KEY) if InfinityKernel.GROQ_KEY else None

    async def ask_professor(self, prompt: str, history: list = None) -> str:
        if not self.client: return "🔴 AI Serveri ulanmagan."
        
        try:
            messages = [{"role": "system", "content": "Siz Logos Akademiyasining oliy aqlli professorisiz. Foydalanuvchiga juda aniq va ilmiy javob bering."}]
            if history: messages.extend(history)
            messages.append({"role": "user", "content": prompt})

            completion = self.client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
                temperature=0.8,
                max_tokens=1500
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"⚠️ Xatolik yuz berdi: {str(e)}"

neural = NeuralCore()

# ==========================================================================================
# 🎭 STATES & INTERFACE
# ==========================================================================================
class BotStates(StatesGroup):
    registration = State()
    ai_chat = State()
    support = State()
    admin_broadcast = State()

class UI:
    @staticmethod
    def main_menu(uid: int):
        builder = ReplyKeyboardBuilder()
        builder.add(KeyboardButton(text="🧠 AI PROFESSOR"), KeyboardButton(text="👤 PROFIL"))
        builder.add(KeyboardButton(text="🏆 REYTING"), KeyboardButton(text="💰 BOZOR"))
        builder.add(KeyboardButton(text="🎁 BONUS"), KeyboardButton(text="⚙️ SOZLAMALAR"))
        if uid in InfinityKernel.ADMINS:
            builder.add(KeyboardButton(text="👑 ADMIN PANEL"))
        builder.adjust(2)
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def profile_inline():
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Balansni to'ldirish", callback_data="deposit")
        kb.button(text="🔄 Prestige yangilash", callback_data="upgrade_prestige")
        kb.adjust(1)
        return kb.as_markup()

# ==========================================================================================
# ⚡️ CORE LOGIC (HANDLERS)
# ==========================================================================================
bot = Bot(token=InfinityKernel.TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    uid = message.from_user.id
    user = db.execute("SELECT * FROM users WHERE uid = ?", (uid,), fetch="one")

    if not user:
        # Yangi foydalanuvchi registratsiyasi
        args = message.text.split()
        ref_by = args[1] if len(args) > 1 and args[1].isdigit() else None
        
        db.execute(
            "INSERT INTO users (uid, fullname, username, referred_by) VALUES (?,?,?,?)",
            (uid, message.from_user.full_name, message.from_user.username, ref_by)
        )
        
        if ref_by:
            db.execute("UPDATE users SET gold = gold + ? WHERE uid = ?", 
                       (InfinityKernel.ECONOMY["REF_REWARD_GOLD"], int(ref_by)))
            try:
                await bot.send_message(int(ref_by), f"🎊 Sizda yangi hamkor! +{InfinityKernel.ECONOMY['REF_REWARD_GOLD']} oltin berildi.")
            except: pass

        await message.answer(f"{InfinityKernel.THEME['HEADER']}\nInfinity tizimiga xush kelibsiz!", reply_markup=UI.main_menu(uid))
    else:
        await message.answer(f"Xush kelibsiz, <b>{user['fullname']}</b>!", reply_markup=UI.main_menu(uid))

@dp.message(F.text == "👤 PROFIL")
async def profile_handler(message: Message):
    u = db.execute("SELECT * FROM users WHERE uid = ?", (message.from_user.id,), fetch="one")
    text = (
        f"{InfinityKernel.THEME['HEADER']}\n"
        f"{InfinityKernel.THEME['DIVIDER']}\n"
        f"👤 Foydalanuvchi: <b>{u['fullname']}</b>\n"
        f"🆔 ID: <code>{u['uid']}</code>\n"
        f"{InfinityKernel.THEME['DIVIDER']}\n"
        f"{InfinityKernel.THEME['GOLD']} Oltin: <b>{u['gold']:,}</b>\n"
        f"{InfinityKernel.THEME['XP']} Tajriba: <b>{u['xp']} XP</b> (Lvl: {u['level']})\n"
        f"{InfinityKernel.THEME['ENERGY']} Energiya: <b>{u['energy']}/100</b>\n"
        f"🎖 Status: <b>{u['status']}</b>\n"
        f"{InfinityKernel.THEME['DIVIDER']}\n"
    )
    await message.answer(text, reply_markup=UI.profile_inline())

@dp.message(F.text == "🧠 AI PROFESSOR")
async def ai_init(message: Message, state: FSMContext):
    u = db.execute("SELECT energy FROM users WHERE uid = ?", (message.from_user.id,), fetch="one")
    if u['energy'] < InfinityKernel.ECONOMY["AI_COST"]:
        return await message.answer("⚠️ Energiyangiz yetarli emas! Biroz kuting yoki sotib oling.")
    
    await state.set_state(BotStates.ai_chat)
    await message.answer(f"{InfinityKernel.THEME['AI']} <b>Professor bilan aloqa o'rnatildi.</b>\nSavolingizni yuboring (Chiqish uchun /cancel):")

@dp.message(BotStates.ai_chat)
async def ai_process(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        return await message.answer("Muloqot yakunlandi.", reply_markup=UI.main_menu(message.from_user.id))
    
    wait_msg = await message.answer("🔄 <i>Professor o'ylamoqda...</i>")
    
    # AI javobi
    response = await neural.ask_professor(message.text)
    
    # Ekonomika yangilanishi
    db.execute("UPDATE users SET energy = energy - ?, xp = xp + ? WHERE uid = ?", 
               (InfinityKernel.ECONOMY["AI_COST"], InfinityKernel.ECONOMY["AI_REWARD_XP"], message.from_user.id))
    
    await wait_msg.edit_text(response)

@dp.message(F.text == "🎁 BONUS")
async def bonus_handler(message: Message):
    uid = message.from_user.id
    today = datetime.date.today()
    check = db.execute("SELECT * FROM bonus_logs WHERE uid = ?", (uid,), fetch="one")
    
    if check and check['last_claim'] == str(today):
        return await message.answer("❌ Bugun bonus olgansiz. Ertaga qaytib keling!")
    
    reward = random.randint(InfinityKernel.ECONOMY["DAILY_BONUS_MIN"], InfinityKernel.ECONOMY["DAILY_BONUS_MAX"])
    
    if not check:
        db.execute("INSERT INTO bonus_logs (uid, last_claim) VALUES (?,?)", (uid, today))
    else:
        db.execute("UPDATE bonus_logs SET last_claim = ? WHERE uid = ?", (today, uid))
        
    db.execute("UPDATE users SET gold = gold + ? WHERE uid = ?", (reward, uid))
    await message.answer(f"🎁 Tabriklaymiz! Sizga <b>{reward}</b> oltin berildi.")

# ==========================================================================================
# 🌐 PRODUCTION WEB SERVER (ANTI-SLEEP)
# ==========================================================================================
app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        "status": "active", 
        "version": InfinityKernel.VERSION,
        "engine": "Infinity Quantum Engine",
        "time": str(datetime.datetime.now())
    })

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==========================================================================================
# 🚀 SYSTEM LAUNCHER
# ==========================================================================================
async def start_system():
    # Flaskni alohida oqimda ishga tushirish
    threading.Thread(target=run_flask, daemon=True).start()
    
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Bot buyruqlari
    await bot.set_my_commands([
        BotCommand(command="start", description="Tizimni qayta ishga tushirish"),
        BotCommand(command="profile", description="Profilingiz"),
        BotCommand(command="help", description="Yordam markazi")
    ])
    
    print(f"--- LOGOS INFINITY {InfinityKernel.VERSION} IS RUNNING ---")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(start_system())
    except (KeyboardInterrupt, SystemExit):
        logging.critical("Siztema to'xtatildi.")
