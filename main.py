import os
import sys
import json
import sqlite3
import asyncio
import logging
from datetime import datetime
from aiohttp import web
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramAPIError

# ==========================================
# 1. ENVIRONMENT VA CONFIGURATSIYA
# ==========================================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PORT = int(os.getenv("PORT", 10000))  # Render avtomatik PORT beradi
APP_ENV = os.getenv("APP_ENV", "production")

# Logging sozlamalari (Professional, xavfsiz)
logging.basicConfig(
    level=logging.INFO if APP_ENV == "production" else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ==========================================
# 2. DATABASE (MA'LUMOTLAR BAZASI) ARXITEKTURASI
# ==========================================
DB_PATH = "edu_platform.db"

def init_db():
    """Barcha kerakli jadvallarni yaratish (SQLite / Kelajakda Postgres)"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Users jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    streak INTEGER DEFAULT 0,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tests jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tests (
                    test_code TEXT PRIMARY KEY,
                    title TEXT,
                    category TEXT,
                    difficulty TEXT,
                    correct_answers TEXT,
                    pdf_file_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Results jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    test_code TEXT,
                    score INTEGER,
                    percentage REAL,
                    wrong_answers TEXT,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(test_code) REFERENCES tests(test_code),
                    UNIQUE(user_id, test_code)
                )
            ''')
            
            # Analytics jadvali
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT,
                    user_id INTEGER,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("Database jadvallari muvaffaqiyatli tekshirildi/yaratildi.")
    except Exception as e:
        logger.critical(f"Database xatoligi: {e}")
        sys.exit(1) # DB siz bot ishlamasligi kerak

# Database yordamchi funksiyalari
def execute_query(query, params=(), fetch=False, fetchall=False):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch:
            return cursor.fetchone()
        if fetchall:
            return cursor.fetchall()
        conn.commit()
        return cursor.lastrowid

# ==========================================
# 3. FSM (HOLATLAR)
# ==========================================
class UserStates(StatesGroup):
    main_menu = State()
    waiting_for_test_code = State()
    solving_test = State()
    ai_tutor_chat = State()
    contact_admin = State()

class AdminStates(StatesGroup):
    admin_menu = State()
    add_test_code = State()
    add_test_answers = State()
    add_test_pdf = State()
    broadcast_message = State()

# ==========================================
# 4. KEYBOARDS (UI/UX DIZAYN)
# ==========================================
def get_main_menu_kb() -> ReplyKeyboardMarkup:
    """Asosiy menyu - Premium, toza va tushunarli"""
    kb = [
        [KeyboardButton(text="📝 Testlar ro'yxati"), KeyboardButton(text="✅ Test tekshirish")],
        [KeyboardButton(text="🤖 AI Ustoz"), KeyboardButton(text="📊 Natijalarim")],
        [KeyboardButton(text="👤 Profilim"), KeyboardButton(text="📞 Bog'lanish")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, input_field_placeholder="Quyidagilardan birini tanlang...")

def get_back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🏠 Bosh menyu")]], resize_keyboard=True)

def get_inline_test_actions(test_code: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🚀 Testni ishlash", callback_data=f"start_test_{test_code}")],
        [InlineKeyboardButton(text="💾 Saqlash (Favorites)", callback_data=f"fav_{test_code}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_ai_tutor_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📸 Rasmli savol yuborish", callback_data="ai_image_tutor")],
        [InlineKeyboardButton(text="❌ Yakunlash", callback_data="ai_tutor_exit")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ==========================================
# 5. CORE LOGIC VA SERVISLAR
# ==========================================
def calculate_test_result(user_answers: str, correct_answers: str) -> dict:
    """Test natijalarini hisoblash servisi"""
    user_ans_list = list(user_answers.upper())
    corr_ans_list = list(correct_answers.upper())
    
    total = len(corr_ans_list)
    correct = 0
    wrong_details = []
    
    for i in range(min(len(user_ans_list), total)):
        if user_ans_list[i] == corr_ans_list[i]:
            correct += 1
        else:
            wrong_details.append(f"{i+1}-savol: Siz: {user_ans_list[i]} | To'g'ri: {corr_ans_list[i]}")
            
    percentage = (correct / total) * 100 if total > 0 else 0
    return {
        "score": correct,
        "total": total,
        "percentage": round(percentage, 2),
        "wrong_details": "\n".join(wrong_details)
    }

def update_user_gamification(user_id: int, percentage: float):
    """XP va Level tizimi dvigateli"""
    xp_gained = int(percentage * 10)  # 100% = 1000 XP
    user = execute_query("SELECT xp, level FROM users WHERE user_id = ?", (user_id,), fetch=True)
    if user:
        current_xp = user[0] + xp_gained
        new_level = (current_xp // 5000) + 1  # Har 5000 XP da yangi level
        execute_query("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (current_xp, new_level, user_id))
        return xp_gained, new_level
    return 0, 1

# ==========================================
# 6. ROUTERLAR VA HANDLERLAR
# ==========================================
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Start komandasi - Foydalanuvchini ro'yxatga olish"""
    user_id = message.from_user.id
    username = message.from_user.username or "Noma'lum"
    full_name = message.from_user.full_name
    
    # DB ga qo'shish (agar yo'q bo'lsa)
    execute_query(
        "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
        (user_id, username, full_name)
    )
    
    await state.clear()
    welcome_text = (
        f"Assalomu alaykum, <b>{html.escape(full_name)}</b>! 🎯\n\n"
        f"Men premium darajadagi <b>Math Tekshiruvchi Bot</b>man.\n"
        f"Bilimingizni sinab ko'ring, AI ustoz bilan xatolaringizni tahlil qiling va Global reytingda yetakchi bo'ling!"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu_kb())

@router.message(F.text == "🏠 Bosh menyu")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bosh menyuga qaytdik. Nima qilamiz?", reply_markup=get_main_menu_kb())

# --- PROFIL MODULI ---
@router.message(F.text == "👤 Profilim")
async def show_profile(message: Message):
    user_id = message.from_user.id
    user = execute_query("SELECT xp, level, streak FROM users WHERE user_id = ?", (user_id,), fetch=True)
    
    if user:
        xp, level, streak = user
        # Natijalar statistikasini olish
        stats = execute_query("SELECT COUNT(*), AVG(percentage) FROM results WHERE user_id = ?", (user_id,), fetch=True)
        total_tests = stats[0] or 0
        avg_score = round(stats[1] or 0, 1)
        
        profile_text = (
            f"👤 <b>PROFIL MA'LUMOTLARI</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"🏆 <b>Level:</b> {level} (🌟 {xp} XP)\n"
            f"🔥 <b>Streak:</b> {streak} kun\n\n"
            f"📊 <b>Statistika:</b>\n"
            f"• Ishlangan testlar: {total_tests} ta\n"
            f"• O'rtacha aniqlik: {avg_score}%\n"
        )
        await message.answer(profile_text, reply_markup=get_main_menu_kb())
    else:
        await message.answer("Profil ma'lumotlari topilmadi. /start ni bosing.")

# --- TESTLAR RO'YXATI MODULI ---
@router.message(F.text == "📝 Testlar ro'yxati")
async def list_tests(message: Message):
    # Pagination va Filterlash mantiqi shu yerda bo'ladi
    tests = execute_query("SELECT test_code, title, difficulty FROM tests ORDER BY created_at DESC LIMIT 5", fetchall=True)
    
    if not tests:
        await message.answer("Hozircha tizimda testlar mavjud emas. 📭", reply_markup=get_main_menu_kb())
        return

    text = "📚 <b>Eng so'nggi testlar:</b>\n\n"
    for t in tests:
        text += f"🔖 Kod: <code>{t[0]}</code> | 📊 {t[2]}\n📘 {t[1]}\n\n"
    
    text += "Test kodi orqali '✅ Test tekshirish' bo'limida natijangizni bilib olishingiz mumkin."
    await message.answer(text, reply_markup=get_main_menu_kb())

# --- TEST TEKSHIRISH MODULI ---
@router.message(F.text == "✅ Test tekshirish")
async def init_test_check(message: Message, state: FSMContext):
    await message.answer(
        "🔍 <b>Test kodini kiriting:</b>\n"
        "(Masalan: <i>1024</i>)", 
        reply_markup=get_back_kb()
    )
    await state.set_state(UserStates.waiting_for_test_code)

@router.message(UserStates.waiting_for_test_code, F.text)
async def process_test_code(message: Message, state: FSMContext):
    test_code = message.text.strip()
    test = execute_query("SELECT test_code, title, correct_answers, pdf_file_id FROM tests WHERE test_code = ?", (test_code,), fetch=True)
    
    if not test:
        await message.answer("❌ Bunday kodli test topilmadi. Iltimos, qayta urinib ko'ring yoki ro'yxatdan qarab oling.")
        return
    
    # 1 marta ishlash cheklovi (One-user-one-test enforcement)
    prev_result = execute_query("SELECT id FROM results WHERE user_id = ? AND test_code = ?", (message.from_user.id, test_code), fetch=True)
    if prev_result:
        await message.answer("⚠️ Siz bu testni allaqachon ishlagansiz! Natijalaringizni '📊 Natijalarim' bo'limidan ko'rishingiz mumkin.", reply_markup=get_main_menu_kb())
        await state.clear()
        return

    await state.update_data(test_code=test[0], correct_answers=test[2])
    
    # PDF yuborish mantiqi (agar mavjud bo'lsa)
    if test[3]:
        try:
            await message.bot.send_document(chat_id=message.from_user.id, document=test[3], caption=f"📄 {test[1]} test materiallari")
        except Exception as e:
            logger.error(f"PDF yuborishda xatolik: {e}")
            
    await message.answer(
        f"✅ Test topildi: <b>{test[1]}</b>\n\n"
        f"Savollar soni: {len(test[2])} ta.\n\n"
        f"✏️ Javoblaringizni yuboring (Masalan: <i>abcdabcd...</i>):",
        reply_markup=get_back_kb()
    )
    await state.set_state(UserStates.solving_test)

@router.message(UserStates.solving_test, F.text)
async def check_test_answers(message: Message, state: FSMContext):
    user_answers = message.text.strip().replace(" ", "")
    data = await state.get_data()
    test_code = data.get("test_code")
    correct_answers = data.get("correct_answers")
    
    if len(user_answers) != len(correct_answers):
        await message.answer(f"⚠️ Javoblar soni mos emas! Testda {len(correct_answers)} ta savol bor. Siz {len(user_answers)} ta yubordingiz. Qaytadan kiriting:")
        return

    # Natijani hisoblash
    result = calculate_test_result(user_answers, correct_answers)
    
    # DB ga saqlash
    try:
        execute_query(
            "INSERT INTO results (user_id, test_code, score, percentage, wrong_answers) VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, test_code, result['score'], result['percentage'], result['wrong_details'])
        )
    except sqlite3.IntegrityError:
        pass # Duplicate catch

    # Gamification
    xp, new_level = update_user_gamification(message.from_user.id, result['percentage'])
    
    # Chiroyli Natija Kartasi
    response_text = (
        f"📊 <b>TEST NATIJASI:</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>To'g'ri javoblar:</b> {result['score']} / {result['total']}\n"
        f"📈 <b>Foiz:</b> {result['percentage']}%\n\n"
        f"🎁 <b>Yutuqlar:</b> +{xp} XP\n"
        f"🌟 <b>Joriy Level:</b> {new_level}\n\n"
    )
    
    if result['wrong_details']:
        response_text += f"❌ <b>Xatolaringiz:</b>\n<code>{result['wrong_details']}</code>\n\n"
        response_text += "🤖 <i>Xatolaringizni tushunish uchun 'AI Ustoz' bo'limiga o'ting!</i>"
    else:
        response_text += "🏆 <b>MUKAMMAL! Siz barcha savollarga to'g'ri javob berdingiz!</b>"

    await message.answer(response_text, reply_markup=get_main_menu_kb())
    await state.clear()

# --- AI USTOZ MODULI (Multimodal xavfsiz integratsiya asosi) ---
@router.message(F.text == "🤖 AI Ustoz")
async def start_ai_tutor(message: Message, state: FSMContext):
    await message.answer(
        "🧠 <b>AI Ustozga xush kelibsiz!</b>\n\n"
        "Men sizga har qanday misolni step-by-step tushuntirib beraman.\n"
        "Matnli savol yozing, rasm yuboring yoki ovozli xabar qoldiring (Ovozli xabarlar tez orada ishga tushadi).\n\n"
        "<i>Eslatma: Murakkab matematik formulalarni rasmga olib yuborishingiz mumkin.</i>",
        reply_markup=get_ai_tutor_kb()
    )
    await state.set_state(UserStates.ai_tutor_chat)

@router.message(UserStates.ai_tutor_chat)
async def process_ai_request(message: Message, state: FSMContext):
    # Bu yerda Gemini yoki OpenAI API ulanishi bo'ladi.
    # Fallback/Placeholder logic:
    if message.text == "❌ Yakunlash":
        await state.clear()
        await message.answer("AI Ustoz bilan suhbat yakunlandi.", reply_markup=get_main_menu_kb())
        return

    # Graceful fallback javob (API ishlamaganda yoki ulanmaganda tizim buzilmaydi)
    placeholder_response = (
        "🤖 AI Ustoz: Hozirgi vaqtda so'rovingiz qabul qilindi.\n"
        "<i>(Bu yerda AI modeli (masalan, Gemini 1.5 Pro) sizning darsingizni vizual yoki matnli tahlil qilib, qadamma-qadam tushuntirib beradi. "
        "Production serverda API kalitlar orqali ushbu modul aktivlashtiriladi.)</i>"
    )
    await message.answer(placeholder_response)

# --- GLOBAL ERROR HANDLING (Middleware o'rniga Exception Handler) ---
@router.errors()
async def global_error_handler(update, exception):
    """Xatolarni ushlash va log qilish - Bot yiqilmaydi"""
    logger.error(f"Kutilmagan xatolik: {exception} | Update: {update}")
    # Agar xato xabarga bog'liq bo'lsa, foydalanuvchiga fallback xabar beramiz
    if update.message:
        await update.message.answer("⚠️ Tizimda qisqa muddatli nosozlik yuz berdi. Iltimos, /start buyrug'ini bosing yoki birozdan so'ng qayta urinib ko'ring.")
    return True

# ==========================================
# 7. RENDER VA VPS UCHUN WEB SERVER (HEALTH CHECK)
# ==========================================
async def handle_health_check(request):
    """Render port tekshiruvidan o'tish uchun 200 OK qaytaradi"""
    return web.Response(text="Bot is running smoothly!", status=200)

async def start_web_server():
    """Veb serverni orqa fonda ishga tushirish"""
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    app.router.add_get('/health', handle_health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"Web server port {PORT} da ishga tushdi (Render uchun).")

# ==========================================
# 8. MAIN ENTRYPOINT
# ==========================================
async def main():
    # DB ni tayyorlash
    init_db()
    
    # Bot va Dispatcherni initsializatsiya qilish
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    
    # Routerlarni ulash
    dp.include_router(router)
    
    # Web serverni parallel ishga tushirish (Render Crash Prevention)
    await start_web_server()
    
    try:
        logger.info("Bot polling orqali ishga tushirildi...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Bot ishida jiddiy xatolik: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        # Eski asyncio loop xatoliklarini oldini olish (Windows/Linux muvofiqligi)
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot faoliyati to'xtatildi (Graceful Shutdown).")
