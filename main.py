import asyncio
import logging
import os
import datetime
import random
from typing import Final, List, Optional, Any, Dict

# --- AIOGRAM PROFESSIONAL STACK ---
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import (
    Message, BotCommand, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# --- ASYNC WEB & DB & AI ---
from aiohttp import web
import aiosqlite
from groq import AsyncGroq
from dotenv import load_dotenv

# .env faylni o'qish (lokal test uchun)
load_dotenv()

# ==========================================================================================
# 💎 TITAN OMNI KERNEL V17 (ENTERPRISE EDITION)
# ==========================================================================================
class Config:
    VERSION: Final[str] = "v17.0.TITAN.ENTERPRISE"
    BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN", "BU_YERGA_TOKEN_YOZING")
    GROQ_KEY: Final[str] = os.getenv("GROQ_API_KEY", "BU_YERGA_GROQ_API_YOZING")
    ADMINS: Final[List[int]] = [8588645504] # O'zingizning ID raqamingiz
    DB_NAME: str = "titan_enterprise.db"
    
    # RENDER WEBHOOK SOZLAMALARI
    WEB_SERVER_HOST: str = "0.0.0.0"
    WEB_SERVER_PORT: int = int(os.getenv("PORT", 8080))
    WEBHOOK_PATH: str = f"/webhook/{BOT_TOKEN}"
    BASE_WEBHOOK_URL: str = os.getenv("RENDER_EXTERNAL_URL", "https://sizning-loyiha.onrender.com")
    
    ECONOMY = {
        "START_GOLD": 1000,
        "QUERY_XP": 50,
        "REFERRAL_GOLD": 1500,
        "REFERRAL_XP": 2000,
        "DAILY_BONUS_MIN": 200,
        "DAILY_BONUS_MAX": 1500,
    }
    LOGO = "🌌 <b>TITAN OMNI SYSTEM</b>"
    DIV = "<b>" + "━"*25 + "</b>"

# ==========================================================================================
# 🗄️ ASYNC DATA ENGINE (Bloklanmaydigan ma'lumotlar bazasi)
# ==========================================================================================
class AsyncDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uid INTEGER PRIMARY KEY,
                    name TEXT,
                    username TEXT,
                    gold REAL DEFAULT 1000,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    referrals INTEGER DEFAULT 0,
                    referred_by INTEGER,
                    status TEXT DEFAULT 'active',
                    last_bonus DATE,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sys_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid INTEGER,
                    action TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def get_user(self, uid: int) -> Optional[aiosqlite.Row]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE uid = ?", (uid,)) as cursor:
                return await cursor.fetchone()

    async def add_user(self, uid: int, name: str, username: str, ref_id: int = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (uid, name, username, referred_by) VALUES (?, ?, ?, ?)",
                (uid, name, username, ref_id)
            )
            if ref_id:
                # Referal egasiga bonus berish
                await db.execute(
                    "UPDATE users SET gold = gold + ?, xp = xp + ?, referrals = referrals + 1 WHERE uid = ?",
                    (Config.ECONOMY["REFERRAL_GOLD"], Config.ECONOMY["REFERRAL_XP"], ref_id)
                )
            await db.commit()

    async def update_balance(self, uid: int, gold: int = 0, xp: int = 0):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET gold = gold + ?, xp = xp + ? WHERE uid = ?", (gold, xp, uid))
            await db.commit()

    async def claim_daily_bonus(self, uid: int) -> int:
        today = datetime.date.today().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT last_bonus FROM users WHERE uid = ?", (uid,)) as cursor:
                user = await cursor.fetchone()
                
            if user and user["last_bonus"] == today:
                return 0 # Bonus olingan
                
            bonus_amount = random.randint(Config.ECONOMY["DAILY_BONUS_MIN"], Config.ECONOMY["DAILY_BONUS_MAX"])
            await db.execute("UPDATE users SET gold = gold + ?, last_bonus = ? WHERE uid = ?", (bonus_amount, today, uid))
            await db.commit()
            return bonus_amount

    async def get_top_users(self, limit: int = 5) -> List[aiosqlite.Row]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT name, xp, gold FROM users ORDER BY xp DESC LIMIT ?", (limit,)) as cursor:
                return await cursor.fetchall()

db = AsyncDatabase(Config.DB_NAME)

# ==========================================================================================
# 🧠 TITAN NEURAL CORE (Asinxron AI)
# ==========================================================================================
class AIEngine:
    def __init__(self):
        self.client = AsyncGroq(api_key=Config.GROQ_KEY) if Config.GROQ_KEY else None

    async def generate(self, prompt: str) -> str:
        if not self.client: return "🔴 AI moduli API kaliti yo'qligi sababli faolsizlantirilgan."
        try:
            chat_completion = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Siz Titan OMNI tizimining professorisiz. Qisqa, aniq va foydali javob bering."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=1024
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logging.error(f"AI Xatosi: {e}")
            return f"⚠️ Vaqtinchalik neyrotarmoq xatosi yuz berdi. Iltimos keyinroq urinib ko'ring."

ai = AIEngine()

# ==========================================================================================
# 🎮 INTERFACE & STATES
# ==========================================================================================
class TitanStates(StatesGroup):
    ai_chat = State()
    admin_broadcast = State()

class UI:
    @staticmethod
    def main_menu(uid: int) -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.row(KeyboardButton(text="🧠 AI PROFESSOR"), KeyboardButton(text="👤 PROFIL"))
        builder.row(KeyboardButton(text="🎁 KUNLIK BONUS"), KeyboardButton(text="🏆 REYTING"))
        builder.row(KeyboardButton(text="👥 HAMKORLIK (REFERAL)"))
        if uid in Config.ADMINS:
            builder.row(KeyboardButton(text="👑 ADMIN PANEL"))
        return builder.as_markup(resize_keyboard=True)
    
    @staticmethod
    def cancel_menu() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ BEKOR QILISH")]],
            resize_keyboard=True
        )

# ==========================================================================================
# 🚀 BOT HANDLERS
# ==========================================================================================
bot = Bot(token=Config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    user = await db.get_user(uid)
    
    if not user:
        args = message.text.split()
        ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() and int(args[1]) != uid else None
        
        await db.add_user(uid, message.from_user.full_name, message.from_user.username, ref_id)
        
        if ref_id:
            try:
                await bot.send_message(ref_id, f"🎊 <b>Yangi hamkor qo'shildi!</b>\nSizga {Config.ECONOMY['REFERRAL_GOLD']} Oltin va {Config.ECONOMY['REFERRAL_XP']} XP berildi.")
            except Exception: pass
            
        await message.answer(
            f"{Config.LOGO}\n{Config.DIV}\nXush kelibsiz, <b>{message.from_user.full_name}</b>!\nTitan Enterprise tizimiga muvaffaqiyatli ro'yxatdan o'tdingiz.",
            reply_markup=UI.main_menu(uid)
        )
    else:
        await message.answer(f"Qaytganingizdan xursandmiz, <b>{user['name']}</b>!", reply_markup=UI.main_menu(uid))

@dp.message(F.text == "👤 PROFIL")
async def show_profile(message: Message):
    u = await db.get_user(message.from_user.id)
    if not u: return
    
    ref_link = f"https://t.me/{(await bot.me()).username}?start={u['uid']}"
    
    text = (
        f"{Config.LOGO}\n{Config.DIV}\n"
        f"👤 Foydalanuvchi: <b>{u['name']}</b>\n"
        f"💠 Daraja: <b>{u['level']}</b>\n"
        f"🪙 Oltinlar: <b>{u['gold']:,.0f}</b>\n"
        f"🎖 XP Balans: <b>{u['xp']:,}</b>\n"
        f"👥 Taklif qilinganlar: <b>{u['referrals']} ta</b>\n\n"
        f"🔗 <b>Sizning referal havolangiz:</b>\n<code>{ref_link}</code>\n"
        f"{Config.DIV}"
    )
    await message.answer(text)

@dp.message(F.text == "🎁 KUNLIK BONUS")
async def get_bonus(message: Message):
    bonus = await db.claim_daily_bonus(message.from_user.id)
    if bonus > 0:
        await message.answer(f"🎉 Tabriklaymiz! Siz bugungi bonusni oldingiz: <b>+{bonus} Oltin</b> 🪙")
    else:
        await message.answer("⚠️ Siz bugungi bonusni allaqachon olgansiz. Ertaga qayta urinib ko'ring!")

@dp.message(F.text == "🏆 REYTING")
async def show_leaderboard(message: Message):
    top_users = await db.get_top_users()
    text = f"🏆 <b>TITAN TOP LIDERLAR</b>\n{Config.DIV}\n"
    
    medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
    for idx, u in enumerate(top_users):
        medal = medals[idx] if idx < len(medals) else "🔸"
        text += f"{medal} <b>{u['name']}</b> — {u['xp']} XP | {u['gold']} 🪙\n"
        
    await message.answer(text)

@dp.message(F.text == "👥 HAMKORLIK (REFERAL)")
async def show_referral(message: Message):
    u = await db.get_user(message.from_user.id)
    bot_info = await bot.me()
    ref_link = f"https://t.me/{bot_info.username}?start={u['uid']}"
    
    text = (
        f"🤝 <b>HAMKORLIK DASTURI</b>\n{Config.DIV}\n"
        f"Do'stlaringizni taklif qiling va katta mukofotlarga ega bo'ling!\n\n"
        f"Har bir faol do'stingiz uchun:\n"
        f"➕ <b>{Config.ECONOMY['REFERRAL_GOLD']} Oltin</b>\n"
        f"➕ <b>{Config.ECONOMY['REFERRAL_XP']} XP</b>\n\n"
        f"🔗 <b>Havolangiz:</b>\n<code>{ref_link}</code>"
    )
    await message.answer(text)

# --- AI CHAT LOGIC ---
@dp.message(F.text == "🧠 AI PROFESSOR")
async def enter_ai_mode(message: Message, state: FSMContext):
    await state.set_state(TitanStates.ai_chat)
    await message.answer(
        "🧠 <b>Neyrotarmoq faollashdi.</b>\n\nMen savollaringizga javob berishga tayyorman. Fikr almashishni tugatish uchun pastdagi tugmani bosing.",
        reply_markup=UI.cancel_menu()
    )

@dp.message(F.text == "❌ BEKOR QILISH", StateFilter("*"))
async def cancel_state(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Asosiy menuga qaytdingiz.", reply_markup=UI.main_menu(message.from_user.id))

@dp.message(StateFilter(TitanStates.ai_chat))
async def process_ai_chat(message: Message):
    wait_msg = await message.answer("<i>📡 Tahlil qilinmoqda...</i>")
    
    response = await ai.generate(message.text)
    await db.update_balance(message.from_user.id, xp=Config.ECONOMY["QUERY_XP"])
    
    await wait_msg.edit_text(response)

# ==========================================================================================
# 🌐 WEBHOOK & RENDER SERVER (Mukammal barqarorlik uchun)
# ==========================================================================================
async def on_startup(bot: Bot):
    await db.init_db()
    await bot.set_my_commands([
        BotCommand(command="start", description="Tizimni ishga tushirish"),
        BotCommand(command="help", description="Yordam paneli")
    ])
    webhook_url = f"{Config.BASE_WEBHOOK_URL}{Config.WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url, drop_pending_updates=True)
    logging.info(f"Webhook o'rnatildi: {webhook_url}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    logging.info("Webhook o'chirildi.")

# Render Health Check uchun oddiy route
async def health_check(request):
    return web.Response(text=f"Titan Enterprise {Config.VERSION} is running smoothly!", status=200)

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Webhook serverini yaratish
    app = web.Application()
    
    # Aiogram webhook handlerni app ga ulash
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=Config.WEBHOOK_PATH)
    
    # Render appni uxlatib qo'ymasligi uchun Health Check route qo'shamiz
    app.router.add_get('/', health_check)
    
    # Startup va Shutdown eventlarni ulash
    setup_application(app, dp, bot=bot)
    app.on_startup.append(lambda _: on_startup(bot))
    app.on_shutdown.append(lambda _: on_shutdown(bot))
    
    # Serverni ishga tushirish
    logging.info(f"Starting web server on {Config.WEB_SERVER_HOST}:{Config.WEB_SERVER_PORT}")
    web.run_app(app, host=Config.WEB_SERVER_HOST, port=Config.WEB_SERVER_PORT)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Tizim kritik xatolik bilan to'xtadi: {e}")
