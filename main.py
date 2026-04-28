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

# --- AIOGRAM 3.X PROFESSIONAL STACK ---
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import (
    Message, BotCommand, CallbackQuery, 
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, 
    InlineKeyboardButton, ErrorEvent, BufferedInputFile
)
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from groq import Groq
from flask import Flask, jsonify
from dotenv import load_dotenv

# Konfiguratsiya
load_dotenv()

# ==========================================================================================
# 💎 TITAN KERNEL: SYSTEM PARAMETERS
# ==========================================================================================
class TitanKernel:
    VERSION: Final[str] = "v20.0.SUPREME.ASCENSION"
    BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN")
    GROQ_KEY: Final[str] = os.getenv("GROQ_API_KEY")
    ADMINS: Final[List[int]] = [8588645504]
    DB_NAME: str = "titan_ascension_v20.db"
    
    # --- COMPLEX ECONOMY ---
    ECONOMY = {
        "START_GOLD": 5000,
        "QUERY_XP": 75,
        "REFERRAL_GOLD": 2500,
        "REFERRAL_XP": 5000,
        "DAILY_MIN": 500,
        "DAILY_MAX": 3000,
        "MINING_RATE_BASE": 0.5, # Har sekundda olinadigan oltin
    }
    
    # --- SHOP ITEMS ---
    MARKET = {
        "processor_v1": {"name": "⚡️ Nano Prosessor", "price": 10000, "boost": 2.0},
        "neural_link": {"name": "🧠 Neyro-Link", "price": 50000, "boost": 10.0},
        "titan_core": {"name": "💠 Titan Yadrosi", "price": 250000, "boost": 60.0}
    }

    START_TIME = datetime.datetime.now()
    DIV = "<b>━━━━━━━━━━━━━━━━━━━━━</b>"
    HEADER = "🌌 <b>TITAN OMNI: ASCENSION</b>"

# ==========================================================================================
# 🗄️ ADVANCED DATA ENGINE (MULTI-THREADED & RELIABLE)
# ==========================================================================================
class DataEngine:
    def __init__(self):
        self.conn = sqlite3.connect(TitanKernel.DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._infrastructure_bootstrap()

    def _infrastructure_bootstrap(self):
        with self.lock:
            with self.conn:
                # 1. FOYDALANUVCHILAR
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        uid INTEGER PRIMARY KEY,
                        name TEXT,
                        username TEXT,
                        gold REAL DEFAULT 5000,
                        xp INTEGER DEFAULT 0,
                        level INTEGER DEFAULT 1,
                        mining_power REAL DEFAULT 1.0,
                        last_mine TIMESTAMP,
                        referred_by INTEGER,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # 2. INVENTAR
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS inventory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        uid INTEGER,
                        item_id TEXT,
                        purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # 3. AI SAVOL-JAVOB LOGLARI
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS neural_logs (
                        id TEXT PRIMARY KEY,
                        uid INTEGER,
                        query TEXT,
                        response TEXT,
                        timestamp TIMESTAMP
                    )
                """)

    def execute(self, sql: str, params: tuple = (), fetch: str = "none"):
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
                logging.error(f"ENGINE_FAULT: {e}")
                return None

db = DataEngine()

# ==========================================================================================
# 🧠 NEURAL CORE: AI PROFESSOR
# ==========================================================================================
class NeuralCore:
    def __init__(self):
        self.client = Groq(api_key=TitanKernel.GROQ_KEY) if TitanKernel.GROQ_KEY else None

    async def chat(self, uid: int, prompt: str) -> str:
        if not self.client: return "🔴 Neural System is Offline."
        try:
            comp = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Siz Titan Akademiyasining Oliy Professori emassiz. Siz ekotizimning bir qismisiz."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7
            )
            ans = comp.choices[0].message.content
            db.execute("INSERT INTO neural_logs VALUES (?,?,?,?,?)",
                      (str(uuid.uuid4()), uid, prompt, ans, datetime.datetime.now()))
            return ans
        except Exception as e:
            return f"⚠️ Aloqa uzildi: {e}"

ai = NeuralCore()

# ==========================================================================================
# 🎭 STATES & INTERFACE
# ==========================================================================================
class OmniStates(StatesGroup):
    registration = State()
    ai_professor = State()
    broadcast = State()

class UI:
    @staticmethod
    def main_menu(uid: int):
        kb = ReplyKeyboardBuilder()
        kb.row(KeyboardButton(text="🧠 AI PROFESSOR"), KeyboardButton(text="👤 PROFIL"))
        kb.row(KeyboardButton(text="⛏ MINING"), KeyboardButton(text="🛒 DO'KON"))
        kb.row(KeyboardButton(text="🏆 REYTING"), KeyboardButton(text="🎁 BONUS"))
        kb.row(KeyboardButton(text="👥 DO'STLAR"), KeyboardButton(text="⚙️ SOZLAMALAR"))
        if uid in TitanKernel.ADMINS:
            kb.row(KeyboardButton(text="👑 SUPREME PANEL"))
        return kb.as_markup(resize_keyboard=True)

    @staticmethod
    def shop_keyboard():
        kb = InlineKeyboardBuilder()
        for k, v in TitanKernel.MARKET.items():
            kb.row(InlineKeyboardButton(text=f"{v['name']} | {v['price']} 🪙", callback_data=f"buy_{k}"))
        return kb.as_markup()

# ==========================================================================================
# 🤖 BOT CORE LOGIC
# ==========================================================================================
bot = Bot(token=TitanKernel.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# --- START & REGISTRATION ---
@dp.message(CommandStart())
async def titan_start(message: Message, state: FSMContext):
    uid = message.from_user.id
    user = db.execute("SELECT * FROM users WHERE uid = ?", (uid,), fetch="one")
    
    if not user:
        args = message.text.split()
        ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        
        db.execute("INSERT INTO users (uid, name, username, referred_by, last_mine) VALUES (?,?,?,?,?)",
                  (uid, message.from_user.full_name, message.from_user.username, ref_id, datetime.datetime.now()))
        
        if ref_id and ref_id != uid:
            db.execute("UPDATE users SET gold = gold + ?, xp = xp + ? WHERE uid = ?",
                      (TitanKernel.ECONOMY["REFERRAL_GOLD"], TitanKernel.ECONOMY["REFERRAL_XP"], ref_id))
            try: await bot.send_message(ref_id, "🎊 <b>Yangi hamkor!</b> Balansga bonus qo'shildi.")
            except: pass

        await message.answer(f"{TitanKernel.HEADER}\n{TitanKernel.DIV}\nTitan Ascension tizimiga xush kelibsiz!", 
                             reply_markup=UI.main_menu(uid))
    else:
        await message.answer(f"Xush kelibsiz, {user['name']}!", reply_markup=UI.main_menu(uid))

# --- MINING SYSTEM ---
@dp.message(F.text == "⛏ MINING")
async def mining_center(message: Message):
    uid = message.from_user.id
    user = db.execute("SELECT * FROM users WHERE uid = ?", (uid,), fetch="one")
    
    now = datetime.datetime.now()
    last_mine = datetime.datetime.strptime(user['last_mine'], "%Y-%m-%d %H:%M:%S.%f")
    seconds_passed = (now - last_mine).total_seconds()
    
    earned = seconds_passed * TitanKernel.ECONOMY["MINING_RATE_BASE"] * user['mining_power']
    
    if earned > 1:
        db.execute("UPDATE users SET gold = gold + ?, last_mine = ? WHERE uid = ?", (earned, now, uid))
        await message.answer(f"⛏ <b>Mining Natijasi:</b>\n{TitanKernel.DIV}\nSiz <b>{earned:.2f}</b> oltin qazib oldingiz!")
    else:
        await message.answer(f"⛏ <b>Mining Faol...</b>\nHozircha juda kam oltin yig'ildi. Biroz kuting.")

# --- PROFILE ---
@dp.message(F.text == "👤 PROFIL")
async def show_profile(message: Message):
    u = db.execute("SELECT * FROM users WHERE uid = ?", (message.from_user.id,), fetch="one")
    items = db.execute("SELECT count(*) as count FROM inventory WHERE uid = ?", (u['uid'],), fetch="one")
    
    text = (
        f"👤 <b>USER ANALYTICS</b>\n{TitanKernel.DIV}\n"
        f"Ism: <b>{u['name']}</b>\n"
        f"Oltin: <b>{u['gold']:.2f} 🪙</b>\n"
        f"XP: <b>{u['xp']}</b>\n"
        f"Quvvat: <b>x{u['mining_power']}</b>\n"
        f"Buyumlar: <b>{items['count']} ta</b>\n"
        f"{TitanKernel.DIV}"
    )
    await message.answer(text)

# --- AI PROFESSOR ---
@dp.message(F.text == "🧠 AI PROFESSOR")
async def ai_init(message: Message, state: FSMContext):
    await state.set_state(OmniStates.ai_professor)
    await message.answer("🧠 <b>Professor bilan aloqa o'rnatildi.</b>\nSavolingizni yuboring (Chiqish: /cancel):")

@dp.message(OmniStates.ai_professor)
async def ai_process(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        return await message.answer("Asosiy menyuga qaytildi.", reply_markup=UI.main_menu(message.from_user.id))
    
    thinking = await message.answer("🔄 <i>Neyrotizim ma'lumotni qayta ishlamoqda...</i>")
    ans = await ai.chat(message.from_user.id, message.text)
    
    db.execute("UPDATE users SET xp = xp + ? WHERE uid = ?", (TitanKernel.ECONOMY["QUERY_XP"], message.from_user.id))
    await thinking.edit_text(ans)

# --- SHOP SYSTEM ---
@dp.message(F.text == "🛒 DO'KON")
async def shop_center(message: Message):
    await message.answer("🛒 <b>Titan Texnologiyalari Do'koni:</b>\nUskunalar mining tezligini oshiradi.", 
                         reply_markup=UI.shop_keyboard())

@dp.callback_query(F.data.startswith("buy_"))
async def process_purchase(callback: CallbackQuery):
    uid = callback.from_user.id
    item_key = callback.data.split("_")[1]
    item = TitanKernel.MARKET[item_key]
    
    user = db.execute("SELECT gold FROM users WHERE uid = ?", (uid,), fetch="one")
    
    if user['gold'] >= item['price']:
        db.execute("UPDATE users SET gold = gold - ?, mining_power = mining_power + ? WHERE uid = ?",
                  (item['price'], item['boost'], uid))
        db.execute("INSERT INTO inventory (uid, item_id) VALUES (?,?)", (uid, item_key))
        await callback.answer("✅ Muvaffaqiyatli xarid qilindi!", show_alert=True)
        await callback.message.edit_text(f"🎁 Siz <b>{item['name']}</b> sotib oldingiz!")
    else:
        await callback.answer("❌ Mablag' yetarli emas!", show_alert=True)

# ==========================================================================================
# 🌐 PRODUCTION WEB SERVER (RENDER KEEP-ALIVE)
# ==========================================================================================
app = Flask(__name__)

@app.route('/')
def live_check():
    return jsonify({
        "status": "OPERATIONAL",
        "system": "TITAN_OMNI_V20",
        "uptime": str(datetime.datetime.now() - TitanKernel.START_TIME),
        "db_health": "OPTIMAL"
    })

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==========================================================================================
# 🚀 SYSTEM BOOTSTRAP (EXECUTION)
# ==========================================================================================
async def titan_engine_startup():
    # Flaskni alohida thread ichida yoqish (Render Port Health Check uchun)
    threading.Thread(target=run_flask, daemon=True).start()
    
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    await bot.set_my_commands([
        BotCommand(command="start", description="Tizimni ishga tushirish"),
        BotCommand(command="profile", description="Shaxsiy statistika"),
        BotCommand(command="help", description="Yordam markazi")
    ])
    
    print(f"--- TITAN OMNI {TitanKernel.VERSION} IS LIVE ---")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(titan_engine_startup())
    except (KeyboardInterrupt, SystemExit):
        print("Tizim to'xtatildi.")
