import os
import sqlite3
import pytz
import re
import logging
import asyncio
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = list(map(int, os.getenv("ADMIN_ID", "").split(","))) if os.getenv("ADMIN_ID") else []
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
EXCHANGE_RATE = float(os.getenv("EXCHANGE_RATE", 1))
RESTRICTED_CATEGORIES = os.getenv("RESTRICTED_CATEGORIES", "").split(",") if os.getenv("RESTRICTED_CATEGORIES") else []
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME")
UZBEKISTAN_TZ = pytz.timezone("Asia/Tashkent")
MIN_DELIVERY_TIME = int(os.getenv("MIN_DELIVERY_TIME", 40))
CARD_NUMBER = os.getenv("CARD_NUMBER")
ADMIN_RESPONSE_TIMEOUT = int(os.getenv("ADMIN_RESPONSE_TIMEOUT", 30))
ITEMS_PER_BATCH = int(os.getenv("ITEMS_PER_BATCH", 5))
DELIVERY_FEE_PER_KM = float(os.getenv("DELIVERY_FEE_PER_KM", 5.0))
MAX_DELIVERY_FEE = float(os.getenv("MAX_DELIVERY_FEE", 40.0))

# Validate required environment variables
required_env_vars = {
    "API_TOKEN": API_TOKEN,
    "ADMIN_ID": os.getenv("ADMIN_ID"),
    "PHONE_NUMBER": PHONE_NUMBER,
    "SUPPORT_USERNAME": SUPPORT_USERNAME,
    "CARD_NUMBER": CARD_NUMBER,
}
for var_name, var_value in required_env_vars.items():
    if not var_value:
        logger.error(f"Missing required environment variable: {var_name}")
        raise ValueError(f"Environment variable {var_name} is not set")

# Language dictionary
LANGUAGES = {
    "uz": {
        "welcome": "🎉 *Xush kelibsiz!* Bizning do'kon botimizga xush kelibsiz! Iltimos, tilni tanlang:",
        "start_ordering": "🛒 Buyurtma boshlash",
        "my_coins": "💰 Mening coinlarim",
        "my_orders": "📦 Mening buyurtmalarim",
        "help": "❓ Yordam",
        "settings": "⚙️ Sozlamalar",
        "choose_language": "🌐 Tilni tanlang",
        "enter_name": "📝 Ismingizni kiriting:",
        "enter_phone": "📞 Telefon raqamingizni kiriting (+998 formatida):",
        "main_menu": "🏠 *Asosiy menyu*",
        "send_location": "📍 Joylashuvingizni yuboring:",
        "choose_store": "🏬 Do'konni tanlang:",
        "choose_category": "📋 Kategoriyani tanlang:",
        "add_to_cart": "➕ Savatga qo'shish",
        "see_cart": "🛒 Savatni ko'rish",
        "add_more": "➕ Yana qo'shish",
        "finish_order": "✅ Buyurtmani yakunlash",
        "go_back": "⬅️ Orqaga",
        "buy_coins": "💸 Coin sotib olish",
        "choose_coin_amount": "💰 Coin miqdorini kiriting (1 coin = 1 UZS, masalan, 20.000 yoki 20000.000):",
        "help_info": f"📞 Admin bilan bog'laning: {SUPPORT_USERNAME}",
        "enter_promo": "🎁 Promo kodni kiriting (o'tkazib yuborish uchun 'skip' deb yozing):",
        "choose_delivery_time": "⏰ Yetkazib berish vaqtini tanlang:",
        "next_slot": "Keyingi mavjud vaqt: {time}",
        "admin_choose": "Admin tanlasin (standart 1 soat)",
        "set_time_myself": "O'zim vaqt belgilayman",
        "enter_delivery_time": "⏰ Yetkazib berish vaqtini kiriting (masalan, 'bugun 13:00' yoki 'ertaga 14:00'):",
        "invalid_delivery_time": "❌ Noto'g'ri vaqt formati. Iltimos, 'bugun HH:MM' yoki 'ertaga HH:MM' formatida kiriting.",
        "delivery_time_too_soon": f"❌ Vaqt {MIN_DELIVERY_TIME} daqiqadan kam bo'lmasligi kerak.",
        "cancel": "🚫 Bekor qilish",
        "choose_payment": "💳 To'lov turini tanlang:",
        "coins": "💰 Coinlar",
        "order_submitted": "✅ Buyurtma yuborildi. Admin tasdiqlashini kuting.",
        "order_confirmed": "🎉 Buyurtmangiz tasdiqlandi! Yetkazib berish vaqti: _{time}_",
        "feedback_prompt": "🌟 Xizmatimiz haqida fikr bildiring va baho bering (1-5):",
        "invalid_feedback": "❌ Iltimos, 1 dan 5 gacha bo'lgan baho kiriting.",
        "invalid_phone": "❌ Noto'g'ri telefon raqami. Iltimos, +998 formatida kiriting.",
        "insufficient_coins": "⚠️ Coinlaringiz yetarli emas. Iltimos, qayta urinib ko'ring.",
        "send_coin_check": f"💳 {CARD_NUMBER} kartasiga {EXCHANGE_RATE} UZS = 1 coin kursi bo'yicha {{amount}} UZS o'tkazing va chekni yuboring:",
        "coin_request_sent": "✅ Chek yuborildi. Admin tasdiqlashini kuting.",
        "pending_coin_request": "⚠️ Sizda allaqachon tasdiqlanmagan coin so'rovi mavjud. Iltimos, admin tasdiqlashini kuting.",
        "admin_menu": "🔧 *Admin paneli*: Do'konni tanlang:",
        "add_product": "➕ Mahsulot qo'shish",
        "view_products": "📋 Mahsulotlarni ko'rish",
        "manage_promos": "🎁 Promo kodlarni boshqarish",
        "enter_product_name": "📝 Mahsulot nomini kiriting:",
        "enter_product_desc": "📜 Mahsulot ta'rifini kiriting:",
        "enter_product_price": "💵 Mahsulot narxini kiriting:",
        "enter_product_category": "📋 Mahsulot kategoriyasini kiriting:",
        "upload_product_image": "🖼️ Mahsulot rasmini yuboring:",
        "product_added": "✅ Mahsulot qo'shildi!",
        "choose_product": "📋 Mahsulotni tanlang:",
        "edit_product": "✏️ Tahrirlash",
        "delete_product": "🗑️ O'chirish",
        "enter_promo_code": "🎁 Yangi promo kodni kiriting:",
        "enter_promo_discount": "📉 Chegirma foizini kiriting (1-100):",
        "enter_promo_max_uses": "🔢 Maksimal foydalanish sonini kiriting:",
        "promo_added": "✅ Promo kod qo'shildi!",
        "choose_promo": "🎁 Promo kodni tanlang:",
        "delete_promo": "🗑️ Promo kodni o'chirish",
        "change_name": "📝 Ismni o'zgartirish",
        "	change_language": "🌐 Tilni o'zgartirish",
        "language_changed": "✅ Til o'zgartirildi!",
        "invalid_promo": "❌ Noto'g'ri promo kod yoki chegirma limitiga yetdi.",
        "order_details": "📦 *Buyurtma*: {order_id}\n👤 Foydalanuvchi: {user_name}\n📞 Telefon: {phone}\n🏬 Do'kon: {store}\n🛍️ Mahsulotlar: {products}\n💳 To'lov: {payment}\n⏰ Yetkazib berish: {delivery}\n💵 Jami: {total} UZS (Yetkazib berish: {delivery_fee} UZS)",
        "confirm_order": "✅ Buyurtmani tasdiqlash",
        "no_products": "⚠️ Mahsulotlar topilmadi.",
        "cart_empty": "🛒 Savat bo'sh.",
        "invalid_coin_amount": "❌ Iltimos, to'g'ri coin miqdorini kiriting (musbat raqam, masalan, 20.000 yoki 20000.000).",
        "error": "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring yoki admin bilan bog'laning: {support}",
        "age_confirmation": "⚠️ Ushbu kategoriyadagi mahsulotlarni sotib olish uchun 21 yoshdan katta bo'lishingiz kerak. Siz 21 yoshdan kattamisiz?",
        "age_yes": "✅ Ha, 21 yoshdan kattaman",
        "age_no": "🚫 Yo'q, 21 yoshdan kichikman",
        "age_denied": "❌ Kechirasiz, ushbu kategoriyaga kirish uchun 21 yoshdan katta bo'lishingiz kerak.",
        "load_more": "➕ Ko'proq ko'rish",
        "cart_contents": "🛒 *Savatdagi mahsulotlar*:\n{items}\n💵 Jami: {total} UZS (Yetkazib berish: {delivery_fee} UZS)",
        "remove_from_cart": "🗑️ {product_name} ni o'chirish",
        "quantity_updated": "✅ Miqdor yangilandi!",
        "total_with_delivery": "💵 Jami: {total} UZS (Yetkazib berish: {delivery_fee} UZS)\n⏰ Yetkazib berish vaqtini tanlang:",
        "coin_request_approved": "🎉 Sizning {amount:.3f} coin so'rovingiz tasdiqlandi!",
        "coin_request_rejected": "❌ Sizning coin so'rovingiz admin tomonidan rad etildi.",
        "search_products": "🔍 Mahsulotlarni qidirish"
    },
    "en": {
        "welcome": "🎉 *Welcome!* Welcome to our store bot! Please select a language:",
        "start_ordering": "🛒 Start Ordering",
        "my_coins": "💰 My Coins",
        "my_orders": "📦 My Orders",
        "help": "❓ Help",
        "settings": "⚙️ Settings",
        "choose_language": "🌐 Choose Language",
        "enter_name": "📝 Enter your name:",
        "enter_phone": "📞 Enter your phone number (+998 format):",
        "main_menu": "🏠 *Main Menu*",
        "send_location": "📍 Send your location:",
        "choose_store": "🏬 Choose a Store:",
        "choose_category": "📋 Choose a Category:",
        "add_to_cart": "➕ Add to Cart",
        "see_cart": "🛒 See Cart",
        "add_more": "➕ Add More",
        "finish_order": "✅ Finish Order",
        "go_back": "⬅️ Go Back",
        "buy_coins": "💸 Buy Coins",
        "choose_coin_amount": "💰 Enter coin amount (1 coin = 1 UZS, e.g., 20.000 or 20000.000):",
        "help_info": f"📞 Contact admin: {SUPPORT_USERNAME}",
        "enter_promo": "🎁 Enter promo code (type 'skip' to skip):",
        "choose_delivery_time": "⏰ Choose Delivery Time:",
        "next_slot": "Next available slot: {time}",
        "admin_choose": "Admin will choose (default 1 hour)",
        "set_time_myself": "Set time myself",
        "enter_delivery_time": "⏰ Enter delivery time (e.g., 'today 13:00' or 'tomorrow 14:00'):",
        "invalid_delivery_time": "❌ Invalid time format. Please enter 'today HH:MM' or 'tomorrow HH:MM'.",
        "delivery_time_too_soon": f"❌ Time must be at least {MIN_DELIVERY_TIME} minutes from now.",
        "cancel": "🚫 Cancel",
        "choose_payment": "💳 Choose Payment Method:",
        "coins": "💰 Coins",
        "order_submitted": "✅ Order submitted. Waiting for admin confirmation.",
        "order_confirmed": "🎉 Your order is confirmed! Delivery time: _{time}_",
        "feedback_prompt": "🌟 Please rate our service (1-5):",
        "invalid_feedback": "❌ Please enter a rating between 1 and 5.",
        "invalid_phone": "❌ Invalid phone number. Please use +998 format.",
        "insufficient_coins": "⚠️ Insufficient coins. Please try again.",
        "send_coin_check": f"💳 Transfer {EXCHANGE_RATE} UZS = 1 coin to {CARD_NUMBER} and send the receipt:",
        "coin_request_sent": "✅ Receipt sent. Waiting for admin confirmation.",
        "pending_coin_request": "⚠️ You already have a pending coin request. Please wait for admin confirmation.",
        "admin_menu": "🔧 *Admin Panel*: Choose Store:",
        "add_product": "➕ Add Product",
        "view_products": "📋 View Products",
        "manage_promos": "🎁 Manage Promo Codes",
        "enter_product_name": "📝 Enter product name:",
        "enter_product_desc": "📜 Enter product description:",
        "enter_product_price": "💵 Enter product price:",
        "enter_product_category": "📋 Enter product category:",
        "upload_product_image": "🖼️ Upload product image:",
        "product_added": "✅ Product added!",
        "choose_product": "📋 Choose Product:",
        "edit_product": "✏️ Edit",
        "delete_product": "🗑️ Delete",
        "enter_promo_code": "🎁 Enter new promo code:",
        "enter_promo_discount": "📉 Enter discount percentage (1-100):",
        "enter_promo_max_uses": "🔢 Enter maximum uses:",
        "promo_added": "✅ Promo code added!",
        "choose_promo": "🎁 Choose Promo Code:",
        "delete_promo": "🗑️ Delete Promo Code",
        "change_name": "📝 Change Name",
        "change_language": "🌐 Change Language",
        "language_changed": "✅ Language changed!",
        "invalid_promo": "❌ Invalid promo code or discount limit reached.",
        "order_details": "📦 *Order*: {order_id}\n👤 User: {user_name}\n📞 Phone: {phone}\n🏬 Store: {store}\n🛍️ Products: {products}\n💳 Payment: {payment}\n⏰ Delivery: {delivery}\n💵 Total: {total} UZS (Delivery: {delivery_fee} UZS)",
        "confirm_order": "✅ Confirm Order",
        "no_products": "⚠️ No products found.",
        "cart_empty": "🛒 Cart is empty.",
        "invalid_coin_amount": "❌ Please enter a valid coin amount (positive number, e.g., 20.000 or 20000.000).",
        "error": "❌ An error occurred. Please try again or contact admin: {support}",
        "age_confirmation": "⚠️ You must be 21+ to purchase items in this category. Are you 21 or older?",
        "age_yes": "✅ Yes, I am 21+",
        "age_no": "🚫 No, I am under 21",
        "age_denied": "❌ Sorry, you must be 21+ to access this category.",
        "load_more": "➕ Load More",
        "cart_contents": "🛒 *Cart Contents*:\n{items}\n💵 Total: {total} UZS (Delivery: {delivery_fee} UZS)",
        "remove_from_cart": "🗑️ Remove {product_name}",
        "quantity_updated": "✅ Quantity updated!",
        "total_with_delivery": "💵 Total: {total} UZS (Delivery: {delivery_fee} UZS)\n⏰ Choose Delivery Time:",
        "coin_request_approved": "🎉 Your coin request for {amount:.3f} coins has been approved!",
        "coin_request_rejected": "❌ Your coin request has been rejected by the admin.",
        "search_products": "🔍 Search Products"
    },
    "ru": {
        "welcome": "🎉 *Добро пожаловать!* Добро пожаловать в наш бот магазина! Пожалуйста, выберите язык:",
        "start_ordering": "🛒 Начать заказ",
        "my_coins": "💰 Мои коины",
        "my_orders": "📦 Мои заказы",
        "help": "❓ Помощь",
        "settings": "⚙️ Настройки",
        "choose_language": "🌐 Выберите язык",
        "enter_name": "📝 Введите ваше имя:",
        "enter_phone": "📞 Введите ваш номер телефона (+998 формат):",
        "main_menu": "🏠 *Главное меню*",
        "send_location": "📍 Отправьте ваше местоположение:",
        "choose_store": "🏬 Выберите магазин:",
        "choose_category": "📋 Выберите категорию:",
        "add_to_cart": "➕ Добавить в корзину",
        "see_cart": "🛒 Посмотреть корзину",
        "add_more": "➕ Добавить еще",
        "finish_order": "✅ Завершить заказ",
        "go_back": "⬅️ Назад",
        "buy_coins": "💸 Купить коины",
        "choose_coin_amount": "💰 Введите количество коинов (1 coin = 1 UZS, например, 20.000 или 20000.000):",
        "help_info": f"📞 Свяжитесь с администратором: {SUPPORT_USERNAME}",
        "enter_promo": "🎁 Введите промокод (для пропуска введите 'skip'):",
        "choose_delivery_time": "⏰ Выберите время доставки:",
        "next_slot": "Следующий доступный слот: {time}",
        "admin_choose": "Администратор выберет (по умолчанию 1 час)",
        "set_time_myself": "Установить время самостоятельно",
        "enter_delivery_time": "⏰ Введите время доставки (например, 'сегодня 13:00' или 'завтра 14:00'):",
        "invalid_delivery_time": "❌ Неверный формат времени. Пожалуйста, введите 'сегодня HH:MM' или 'завтра HH:MM'.",
        "delivery_time_too_soon": f"❌ Время должно быть не менее {MIN_DELIVERY_TIME} минут от текущего.",
        "cancel": "🚫 Отмена",
        "choose_payment": "💳 Выберите способ оплаты:",
        "coins": "💰 Коины",
        "order_submitted": "✅ Заказ отправлен. Ожидайте подтверждения администратора.",
        "order_confirmed": "🎉 Ваш заказ подтвержден! Время доставки: _{time}_",
        "feedback_prompt": "🌟 Пожалуйста, оцените наш сервис (1-5):",
        "invalid_feedback": "❌ Пожалуйста, введите оценку от 1 до 5.",
        "invalid_phone": "❌ Неверный номер телефона. Пожалуйста, используйте формат +998.",
        "insufficient_coins": "⚠️ Недостаточно коинов. Пожалуйста, попробуйте снова.",
        "send_coin_check": f"💳 Переведите {EXCHANGE_RATE} UZS = 1 coin на {CARD_NUMBER} и отправьте чек:",
        "coin_request_sent": "✅ Чек отправлен. Ожидайте подтверждения администратора.",
        "pending_coin_request": "⚠️ У вас уже есть незавершенный запрос на коины. Пожалуйста, дождитесь подтверждения администратора.",
        "admin_menu": "🔧 *Панель администратора*: Выберите магазин:",
        "add_product": "➕ Добавить продукт",
        "view_products": "📋 Просмотреть продукты",
        "manage_promos": "🎁 Управление промокодами",
        "enter_product_name": "📝 Введите название продукта:",
        "enter_product_desc": "📜 Введите описание продукта:",
        "enter_product_price": "💵 Введите цену продукта:",
        "enter_product_category": "📋 Введите категорию продукта:",
        "upload_product_image": "🖼️ Загрузите изображение продукта:",
        "product_added": "✅ Продукт добавлен!",
        "choose_product": "📋 Выберите продукт:",
        "edit_product": "✏️ Редактировать",
        "delete_product": "🗑️ Удалить",
        "enter_promo_code": "🎁 Введите новый промокод:",
        "enter_promo_discount": "📉 Введите процент скидки (1-100):",
        "enter_promo_max_uses": "🔢 Введите максимальное количество использований:",
        "promo_added": "✅ Промокод добавлен!",
        "choose_promo": "🎁 Выберите промокод:",
        "delete_promo": "🗑️ Удалить промокод",
        "change_name": "📝 Изменить имя",
        "change_language": "🌐 Изменить язык",
        "language_changed": "✅ Язык изменен!",
        "invalid_promo": "❌ Неверный промокод или достигнут лимит использования.",
        "order_details": "📦 *Заказ*: {order_id}\n👤 Пользователь: {user_name}\n📞 Телефон: {phone}\n🏬 Магазин: {store}\n🛍️ Продукты: {products}\n💳 Оплата: {payment}\n⏰ Доставка: {delivery}\n💵 Итого: {total} UZS (Доставка: {delivery_fee} UZS)",
        "confirm_order": "✅ Подтвердить заказ",
        "no_products": "⚠️ Продукты не найдены.",
        "cart_empty": "🛒 Корзина пуста.",
        "invalid_coin_amount": "❌ Пожалуйста, введите действительное количество коинов (положительное число, например, 20.000 или 20000.000).",
        "error": "❌ Произошла ошибка. Пожалуйста, попробуйте снова или свяжитесь с администратором: {support}",
        "age_confirmation": "⚠️ Вам должно быть 21+, чтобы покупать товары в этой категории. Вам 21 или больше?",
        "age_yes": "✅ Да, мне 21+",
        "age_no": "🚫 Нет, мне меньше 21",
        "age_denied": "❌ Извините, вам должно быть 21+, чтобы получить доступ к этой категории.",
        "load_more": "➕ Показать больше",
        "cart_contents": "🛒 *Содержимое корзины*:\n{items}\n💵 Total: {total} UZS (Delivery: {delivery_fee} UZS)",
        "remove_from_cart": "🗑️ Удалить {product_name}",
        "quantity_updated": "✅ Количество обновлено!",
        "total_with_delivery": "💵 Total: {total} UZS (Delivery: {delivery_fee} UZS)\n⏰ Choose Delivery Time:",
        "coin_request_approved": "🎉 Ваш запрос на {amount:.3f} коинов одобрен!",
        "coin_request_rejected": "❌ Ваш запрос на коины был отклонен администратором.",
        "search_products": "🔍 Поиск продуктов"
    }
}

# Helper function to log products to text files
def log_product_to_file(product_data):
    store_id = product_data["store_id"]
    file_name = "tsum_products.txt" if store_id == 1 else "sergeli_products.txt"
    try:
        with open(file_name, "a", encoding="utf-8") as f:
            f.write("--- Product Entry ---\n")
            f.write(f"Product ID: {product_data['id']}\n")
            f.write(f"Name: {product_data['name']}\n")
            f.write(f"Description: {product_data['description']}\n")
            f.write(f"Price: {product_data['price']} UZS\n")
            f.write(f"Category: {product_data['category']}\n")
            f.write(f"Image File ID: {product_data['image']}\n")
            f.write(f"Store ID: {store_id}\n")
            f.write(f"Added At: {datetime.now(UZBEKISTAN_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("\n")
    except Exception as e:
        logger.error(f"Failed to write product to {file_name}: {e}")

# Initialize database
def init_db():
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        # Drop and recreate coin_requests table
        c.execute("DROP TABLE IF EXISTS coin_requests")
        # Create tables
        c.execute('''CREATE TABLE IF NOT EXISTS stores
                     (id INTEGER PRIMARY KEY, name TEXT, latitude REAL, longitude REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS products
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT,
                      image TEXT, price REAL, category TEXT, store_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY, name TEXT, phone TEXT, language TEXT, coins REAL DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS orders
                     (order_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, store_id INTEGER,
                      products TEXT, delivery_time TEXT, payment_type TEXT, status TEXT, promo_code TEXT,
                      latitude REAL, longitude REAL, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS coin_requests
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, status TEXT,
                      receipt_file_id TEXT, created_at TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS promo_codes
                     (code TEXT PRIMARY KEY, discount REAL, usage_count INTEGER DEFAULT 0, max_uses INTEGER)''')
        # Add missing columns if they don't exist
        try:
            c.execute("ALTER TABLE orders ADD COLUMN latitude REAL")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE orders ADD COLUMN longitude REAL")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE orders ADD COLUMN created_at TEXT")
        except sqlite3.OperationalError:
            pass
        # Insert sample stores
        c.execute("INSERT OR REPLACE INTO stores (id, name, latitude, longitude) VALUES (?, ?, ?, ?)",
                  (1, "Tsum", 41.3111, 69.2797))
        c.execute("INSERT OR REPLACE INTO stores (id, name, latitude, longitude) VALUES (?, ?, ?, ?)",
                  (2, "Sergeli", 41.2275, 69.2514))
        # Insert sample products
        sample_products = [
            ("Cream A", "Moisturizing cream A", None, 15.0, "cream", 1),
            ("Cream B", "Moisturizing cream B", None, 18.0, "cream", 1),
            ("Cream C", "Moisturizing cream C", None, 20.0, "cream", 1),
        ]
        c.executemany("INSERT OR IGNORE INTO products (name, description, image, price, category, store_id) VALUES (?, ?, ?, ?, ?, ?)",
                      sample_products)
        conn.commit()
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        conn.close()

# Haversine formula for distance calculation
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# Generate dynamic delivery time slot
def get_next_delivery_slot():
    now = datetime.now(UZBEKISTAN_TZ)
    min_time = now + timedelta(minutes=MIN_DELIVERY_TIME)
    minutes = (min_time.minute // 30 + 1) * 30
    if minutes >= 60:
        min_time = min_time.replace(hour=min_time.hour + 1, minute=0)
    else:
        min_time = min_time.replace(minute=minutes)
    return min_time.strftime("Today %H:%M")

# Validate and parse custom delivery time
def parse_delivery_time(text, lang):
    now = datetime.now(UZBEKISTAN_TZ)
    min_time = now + timedelta(minutes=MIN_DELIVERY_TIME)
    day_keywords = {
        "uz": {"today": ["bugun"], "tomorrow": ["ertaga"]},
        "en": {"today": ["today"], "tomorrow": ["tomorrow"]},
        "ru": {"today": ["сегодня"], "tomorrow": ["завтра"]}
    }
    text = text.lower().strip()
    time_pattern = r"(\d{1,2})[:.]?(\d{2})"
    delivery_date = None
    for day, keywords in day_keywords[lang].items():
        for keyword in keywords:
            if keyword in text:
                delivery_date = day
                text = text.replace(keyword, "").strip()
                break
        if delivery_date:
            break
    if not delivery_date:
        return None, LANGUAGES[lang]["invalid_delivery_time"]
    time_match = re.match(time_pattern, text)
    if not time_match:
        return None, LANGUAGES[lang]["invalid_delivery_time"]
    hour, minute = map(int, time_match.groups())
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None, LANGUAGES[lang]["invalid_delivery_time"]
    delivery_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if delivery_date == "tomorrow":
        delivery_datetime += timedelta(days=1)
    if delivery_datetime < min_time:
        return None, LANGUAGES[lang]["delivery_time_too_soon"]
    date_str = "Today" if delivery_date == "today" else "Tomorrow"
    return f"{date_str} {hour:02d}:{minute:02d}", None

# Delete previous message if exists
async def delete_previous_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, force_delete: bool = False):
    last_message_id = context.user_data.get("last_message_id")
    message_type = context.user_data.get("message_type")
    pending_alert = context.user_data.get("pending_alert", False)
    if last_message_id and (force_delete or (message_type == "button" and not pending_alert)):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=last_message_id)
        except TelegramError as e:
            logger.warning(f"Failed to delete message {last_message_id}: {e}")
        context.user_data["last_message_id"] = None
        context.user_data["message_type"] = None
    if force_delete and pending_alert:
        context.user_data["pending_alert"] = False

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}", exc_info=True)
    if update and update.effective_message:
        user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
            user = c.fetchone()
            lang = user[0] if user else "en"
        finally:
            conn.close()
        await delete_previous_message(context, user_id, force_delete=True)
        if context.user_data.get("cart"):
            await show_cart(update.effective_message, context, lang)
        else:
            message = await update.effective_message.reply_text(
                LANGUAGES[lang]["error"].format(support=SUPPORT_USERNAME),
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            context.user_data["state"] = ""
            context.user_data["pending_alert"] = False
            await show_main_menu(update.effective_message, context, lang)
    for admin in ADMIN_ID:
        try:
            await context.bot.send_message(
                admin,
                f"Error for user {user_id if 'user_id' in locals() else 'unknown'}: {context.error}"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin}: {e}")

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    finally:
        conn.close()
    await delete_previous_message(context, user_id)
    if user:
        await show_main_menu(update.message, context, user[3])
    else:
        keyboard = [
            [InlineKeyboardButton("O'zbek", callback_data="lang_uz"),
             InlineKeyboardButton("English", callback_data="lang_en")],
            [InlineKeyboardButton("Русский", callback_data="lang_ru")]
        ]
        message = await update.message.reply_text(
            LANGUAGES["en"]["welcome"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"

async def show_main_menu(message, context: ContextTypes.DEFAULT_TYPE, lang: str):
    keyboard = [
        [InlineKeyboardButton(LANGUAGES[lang]["start_ordering"], callback_data="start_ordering"),
         InlineKeyboardButton(LANGUAGES[lang]["my_coins"], callback_data="my_coins")],
        [InlineKeyboardButton(LANGUAGES[lang]["my_orders"], callback_data="my_orders"),
         InlineKeyboardButton(LANGUAGES[lang]["help"], callback_data="help")],
        [InlineKeyboardButton(LANGUAGES[lang]["settings"], callback_data="settings")]
    ]
    if message.chat_id in ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔧 Admin Panel", callback_data="admin_menu")])
    await delete_previous_message(context, message.chat_id, force_delete=True)
    new_message = await message.reply_text(
        LANGUAGES[lang]["main_menu"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["last_message_id"] = new_message.message_id
    context.user_data["message_type"] = "button"
    context.user_data["pending_alert"] = False

# Show admin panel
async def show_admin_panel(message, context: ContextTypes.DEFAULT_TYPE, lang: str):
    keyboard = [
        [InlineKeyboardButton("ЦУМ", callback_data="admin_store_1"),
         InlineKeyboardButton("Sergeli", callback_data="admin_store_2")]
    ]
    await delete_previous_message(context, message.chat_id)
    new_message = await message.reply_text(
        LANGUAGES[lang]["admin_menu"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["last_message_id"] = new_message.message_id
    context.user_data["message_type"] = "button"

# Show cart contents with corrected price handling
async def show_cart(message, context: ContextTypes.DEFAULT_TYPE, lang: str):
    user_id = message.chat_id
    cart = context.user_data.get("cart", {})
    location = context.user_data.get("location", {})
    store_id = context.user_data.get("store_id", 1)
    if not cart:
        await delete_previous_message(context, user_id)
        new_message = await message.reply_text(
            LANGUAGES[lang]["cart_empty"],
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"store_{store_id}")]]),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = new_message.message_id
        context.user_data["message_type"] = "button"
        return
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        product_ids = [str(pid) for pid in cart.keys()]
        c.execute("SELECT id, name, price FROM products WHERE id IN ({})".format(",".join("?" * len(product_ids))), product_ids)
        products = c.fetchall()
        c.execute("SELECT id, name, latitude, longitude FROM stores")
        stores = c.fetchall()
    finally:
        conn.close()
    items = []
    base_total = 0.0
    for p in products:
        product_id, name, price = p
        quantity = cart[str(product_id)]
        price = round(float(price), 3)
        item_total = round(price * quantity, 3)
        base_total += item_total
        items.append(f"• {name} x{quantity} ({'{:.3f}'.format(item_total)} UZS)")
    delivery_fee = 0.0
    if location and stores:
        user_lat, user_lon = location["latitude"], location["longitude"]
        for store in stores:
            store_id_from_db, _, lat, lon = store
            if store_id_from_db == store_id:
                distance = haversine(user_lat, user_lon, lat, lon)
                distance_km = float(distance)
                delivery_fee = min(distance_km * DELIVERY_FEE_PER_KM, MAX_DELIVERY_FEE)
                break
    total = base_total + delivery_fee
    context.user_data["base_total"] = base_total
    context.user_data["delivery_fee"] = delivery_fee
    keyboard = []
    for p in products:
        product_id = str(p[0])
        keyboard.append([InlineKeyboardButton(LANGUAGES[lang]["remove_from_cart"].format(product_name=p[1]), callback_data=f"remove_from_cart_{product_id}")])
    keyboard.append([
        InlineKeyboardButton(LANGUAGES[lang]["add_more"], callback_data=f"store_{store_id}"),
        InlineKeyboardButton(LANGUAGES[lang]["finish_order"], callback_data="finish_order")
    ])
    keyboard.append([InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"store_{store_id}")])
    await delete_previous_message(context, user_id)
    new_message = await message.reply_text(
        LANGUAGES[lang]["cart_contents"].format(items="\n".join(items), total='{:.3f}'.format(total), delivery_fee='{:.3f}'.format(delivery_fee)),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["last_message_id"] = new_message.message_id
    context.user_data["message_type"] = "button"
    context.user_data["store_id"] = store_id

# Handle button callbacks
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        lang = user[0] if user else context.user_data.get("language", "en")
    finally:
        conn.close()
    if data.startswith("lang_"):
        new_lang = data.split("_")[1]
        context.user_data["language"] = new_lang
        if user:
            conn = sqlite3.connect("store_bot.db")
            try:
                c = conn.cursor()
                c.execute("UPDATE users SET language = ? WHERE user_id = ?", (new_lang, user_id))
                conn.commit()
            finally:
                conn.close()
            await delete_previous_message(context, user_id)
            message = await query.message.reply_text(
                LANGUAGES[new_lang]["language_changed"],
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            await show_main_menu(query.message, context, new_lang)
        else:
            await delete_previous_message(context, user_id)
            message = await query.message.reply_text(
                LANGUAGES[new_lang]["enter_name"],
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            context.user_data["state"] = "awaiting_name"
    elif data == "start_ordering":
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton(LANGUAGES[lang]["send_location"], request_location=True)]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["send_location"],
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
        context.user_data["state"] = "awaiting_location"
    elif data == "my_coins":
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
            coins = c.fetchone()[0]
        finally:
            conn.close()
        keyboard = [
            [InlineKeyboardButton(LANGUAGES[lang]["buy_coins"], callback_data="buy_coins"),
             InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data="main_menu")]
        ]
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            f"💰 *Your coins*: {'{:.3f}'.format(coins)}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
    elif data == "buy_coins":
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT id FROM coin_requests WHERE user_id = ? AND status = 'pending'", (user_id,))
            pending_request = c.fetchone()
            if pending_request:
                await delete_previous_message(context, user_id)
                message = await query.message.reply_text(
                    LANGUAGES[lang]["pending_coin_request"],
                    parse_mode="Markdown"
                )
                context.user_data["last_message_id"] = message.message_id
                context.user_data["message_type"] = "alert"
                return
        finally:
            conn.close()
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["choose_coin_amount"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "awaiting_coin_amount"
    elif data == "help":
        keyboard = [[InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data="main_menu")]]
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["help_info"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
    elif data == "my_orders":
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT order_id, products, delivery_time, status FROM orders WHERE user_id = ?", (user_id,))
            orders = c.fetchall()
        finally:
            conn.close()
        if orders:
            message_text = "\n".join([f"📦 *Order {o[0]}*: {o[1]}\n⏰ {o[2]} ({o[3]})" for o in orders])
        else:
            message_text = LANGUAGES[lang]["cart_empty"]
        keyboard = [[InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data="main_menu")]]
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
    elif data == "settings":
        keyboard = [
            [InlineKeyboardButton(LANGUAGES[lang]["change_name"], callback_data="change_name"),
             InlineKeyboardButton(LANGUAGES[lang]["change_language"], callback_data="change_language")],
            [InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data="main_menu")]
        ]
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["settings"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
    elif data == "change_name":
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["enter_name"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "awaiting_new_name"
    elif data == "change_language":
        keyboard = [
            [InlineKeyboardButton("O'zbek", callback_data="lang_uz"),
             InlineKeyboardButton("English", callback_data="lang_en")],
            [InlineKeyboardButton("Русский", callback_data="lang_ru")]
        ]
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["choose_language"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
    elif data == "main_menu":
        context.user_data["cart"] = {}
        context.user_data["base_total"] = 0
        context.user_data["delivery_fee"] = 0
        await delete_previous_message(context, user_id, force_delete=True)
        await show_main_menu(query.message, context, lang)
    elif data.startswith("store_"):
        store_id = int(data.split("_")[1])
        context.user_data["store_id"] = store_id
        context.user_data["category_offset"] = 0
        await show_categories(query.message, context, lang, store_id)
    elif data.startswith("category_"):
        category = data.split("_", 1)[1]
        if category in RESTRICTED_CATEGORIES:
            context.user_data["pending_category"] = category
            keyboard = [
                [InlineKeyboardButton(LANGUAGES[lang]["age_yes"], callback_data="age_confirm_yes"),
                 InlineKeyboardButton(LANGUAGES[lang]["age_no"], callback_data="age_confirm_no")]
            ]
            await delete_previous_message(context, user_id)
            message = await query.message.reply_text(
                LANGUAGES[lang]["age_confirmation"],
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "button"
        else:
            context.user_data["category"] = category
            context.user_data["product_offset"] = 0
            await show_products(query.message, context, lang)
            context.user_data["pending_alert"] = False
    elif data == "age_confirm_yes":
        context.user_data["age_confirmed"] = True
        category = context.user_data.get("pending_category")
        if category:
            context.user_data["category"] = category
            context.user_data["product_offset"] = 0
            await show_products(query.message, context, lang)
            context.user_data["pending_alert"] = False
    elif data == "age_confirm_no":
        context.user_data["age_confirmed"] = False
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["age_denied"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        await show_categories(query.message, context, lang, context.user_data.get("store_id", 1))
    elif data == "load_more_categories":
        context.user_data["category_offset"] += ITEMS_PER_BATCH
        await show_categories(query.message, context, lang, context.user_data.get("store_id", 1))
    elif data == "load_more_products":
        context.user_data["product_offset"] += ITEMS_PER_BATCH
        await show_products(query.message, context, lang)
    elif data.startswith("add_to_cart_"):
        product_id = str(data.split("_")[3])
        if "cart" not in context.user_data:
            context.user_data["cart"] = {}
        context.user_data["cart"][product_id] = context.user_data["cart"].get(product_id, 0) + 1
        store_id = context.user_data.get("store_id", 1)
        keyboard = [
            [InlineKeyboardButton(LANGUAGES[lang]["add_more"], callback_data=f"store_{store_id}"),
             InlineKeyboardButton(LANGUAGES[lang]["see_cart"], callback_data="see_cart")],
            [InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"category_{context.user_data.get('category', '')}")]
        ]
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            "✅ *Product added to cart!*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
    elif data == "see_cart":
        await show_cart(query.message, context, lang)
    elif data.startswith("remove_from_cart_"):
        product_id = str(data.split("_")[3])
        if "cart" in context.user_data and product_id in context.user_data["cart"]:
            del context.user_data["cart"][product_id]
            if not context.user_data["cart"]:
                await delete_previous_message(context, user_id)
                message = await query.message.reply_text(
                    LANGUAGES[lang]["cart_empty"],
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"store_{context.user_data.get('store_id', 1)}")]]),
                    parse_mode="Markdown"
                )
                context.user_data["last_message_id"] = message.message_id
                context.user_data["message_type"] = "button"
            else:
                await show_cart(query.message, context, lang)
        else:
            await delete_previous_message(context, user_id)
            message = await query.message.reply_text(
                LANGUAGES[lang]["cart_empty"],
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"store_{context.user_data.get('store_id', 1)}")]]),
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "button"
    elif data == "finish_order":
        if not context.user_data.get("cart"):
            await delete_previous_message(context, user_id)
            message = await query.message.reply_text(
                LANGUAGES[lang]["cart_empty"],
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            await show_main_menu(query.message, context, lang)
            return
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["enter_promo"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "awaiting_promo_code"
    elif data == "choose_delivery_admin":
        context.user_data["delivery_time"] = f"Admin will choose (default {MIN_DELIVERY_TIME} min)"
        await choose_payment(query.message, context, lang)
    elif data == "choose_delivery_next":
        context.user_data["delivery_time"] = get_next_delivery_slot()
        await choose_payment(query.message, context, lang)
    elif data == "choose_delivery_custom":
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["enter_delivery_time"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "awaiting_custom_delivery_time"
    elif data == "payment_coins":
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
            coins = c.fetchone()[0]
            base_total = context.user_data.get("base_total", 0)
            delivery_fee = context.user_data.get("delivery_fee", 0)
            total_price = base_total + delivery_fee
            promo_code = context.user_data.get("promo_code")
            if promo_code and promo_code.lower() != "skip":
                c.execute("SELECT discount, usage_count, max_uses FROM promo_codes WHERE code = ?", (promo_code.upper(),))
                promo = c.fetchone()
                if promo and promo[1] < promo[2]:
                    discount = float(promo[0]) / 100.0
                    discounted_base_total = base_total * (1 - discount)
                    total_price = discounted_base_total + delivery_fee
        finally:
            conn.close()
        if coins >= total_price:
            context.user_data["payment_type"] = "coins"
            context.user_data["total_price"] = total_price
            await submit_order(query, context, lang)
        else:
            await delete_previous_message(context, user_id)
            message = await query.message.reply_text(
                LANGUAGES[lang]["insufficient_coins"],
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            await show_cart(query.message, context, lang)
    elif data.startswith("admin_store_"):
        store_id = int(data.split("_")[2])
        context.user_data["admin_store_id"] = store_id
        keyboard = [
            [InlineKeyboardButton(LANGUAGES[lang]["add_product"], callback_data="admin_add_product"),
             InlineKeyboardButton(LANGUAGES[lang]["view_products"], callback_data="admin_view_products")],
            [InlineKeyboardButton(LANGUAGES[lang]["manage_promos"], callback_data="admin_manage_promos"),
             InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data="admin_menu")]
        ]
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["admin_menu"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
    elif data == "admin_menu":
        await show_admin_panel(query.message, context, lang)
    elif data == "admin_add_product":
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["enter_product_name"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "admin_awaiting_product_name"
    elif data == "admin_view_products":
        store_id = context.user_data.get("admin_store_id", 1)
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT id, name FROM products WHERE store_id = ?", (store_id,))
            products = c.fetchall()
        finally:
            conn.close()
        if products:
            keyboard = [[InlineKeyboardButton(f"{p[1]}", callback_data=f"admin_product_{p[0]}")] for p in products]
            keyboard.append([InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"admin_store_{store_id}")])
            await delete_previous_message(context, user_id)
            message = await query.message.reply_text(
                LANGUAGES[lang]["choose_product"],
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "button"
        else:
            keyboard = [[InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"admin_store_{store_id}")]]
            await delete_previous_message(context, user_id)
            message = await query.message.reply_text(
                LANGUAGES[lang]["no_products"],
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
    elif data == "admin_manage_promos":
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT code FROM promo_codes")
            promos = c.fetchall()
        finally:
            conn.close()
        keyboard = [[InlineKeyboardButton(p[0], callback_data=f"admin_promo_{p[0]}")] for p in promos]
        keyboard.append([
            InlineKeyboardButton(LANGUAGES[lang]["add_product"], callback_data="admin_add_promo"),
            InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"admin_store_{context.user_data.get('admin_store_id', 1)}")]
        )
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["choose_promo"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
    elif data == "admin_add_promo":
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["enter_promo_code"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "admin_awaiting_promo_code"
    elif data.startswith("admin_product_"):
        product_id = int(data.split("_")[2])
        keyboard = [
            [InlineKeyboardButton(LANGUAGES[lang]["edit_product"], callback_data=f"admin_edit_product_{product_id}"),
             InlineKeyboardButton(LANGUAGES[lang]["delete_product"], callback_data=f"admin_delete_product_{product_id}")],
            [InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data="admin_view_products")]
        ]
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["choose_product"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
    elif data.startswith("admin_delete_product_"):
        product_id = int(data.split("_")[3])
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("DELETE FROM products WHERE id = ?", (product_id,))
            conn.commit()
        finally:
            conn.close()
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["delete_product"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        await show_admin_panel(query.message, context, lang)
    elif data.startswith("admin_promo_"):
        promo_code = data.split("_", 2)[2]
        keyboard = [
            [InlineKeyboardButton(LANGUAGES[lang]["delete_promo"], callback_data=f"admin_delete_promo_{promo_code}")],
            [InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data="admin_manage_promos")]
        ]
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            f"🎁 *Promo code*: {promo_code}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "button"
    elif data.startswith("admin_delete_promo_"):
        promo_code = data.split("_", 3)[3]
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("DELETE FROM promo_codes WHERE code = ?", (promo_code,))
            conn.commit()
        finally:
            conn.close()
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["delete_promo"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        await show_admin_panel(query.message, context, lang)
    elif data.startswith("confirm_order_"):
        order_id = int(data.split("_")[2])
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT user_id, delivery_time FROM orders WHERE order_id = ?", (order_id,))
            order = c.fetchone()
            if order:
                c.execute("UPDATE orders SET status = 'confirmed' WHERE order_id = ?", (order_id,))
                conn.commit()
                await context.bot.send_message(
                    order[0],
                    LANGUAGES[lang]["order_confirmed"].format(time=order[1]),
                    parse_mode="Markdown"
                )
                await context.bot.send_message(
                    order[0],
                    LANGUAGES[lang]["feedback_prompt"],
                    parse_mode="Markdown"
                )
                context.user_data["state"] = "awaiting_feedback"
                context.user_data["pending_alert"] = False
        finally:
            conn.close()
        await show_admin_panel(query.message, context, lang)
    elif data == "search_products":
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            "🔍 Enter your search query (e.g., product name or description):",
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "awaiting_search_query"
    elif data.startswith("approve_coin_"):
        coin_request_id = int(data.split("_")[2])
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT user_id, amount FROM coin_requests WHERE id = ? AND status = 'pending'", (coin_request_id,))
            request = c.fetchone()
            if request:
                user_id, amount = request
                c.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
                c.execute("UPDATE coin_requests SET status = 'approved' WHERE id = ?", (coin_request_id,))
                conn.commit()
                await context.bot.send_message(
                    user_id,
                    LANGUAGES[lang]["coin_request_approved"].format(amount=amount),
                    parse_mode="Markdown"
                )
                await query.message.reply_text(
                    f"✅ Coin request {coin_request_id} approved for user {user_id}.",
                    parse_mode="Markdown"
                )
            else:
                await query.message.reply_text(
                    "❌ Coin request not found or already processed.",
                    parse_mode="Markdown"
                )
        finally:
            conn.close()
        await show_admin_panel(query.message, context, lang)
    elif data.startswith("reject_coin_"):
        coin_request_id = int(data.split("_")[2])
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT user_id FROM coin_requests WHERE id = ? AND status = 'pending'", (coin_request_id,))
            request = c.fetchone()
            if request:
                user_id = request[0]
                c.execute("UPDATE coin_requests SET status = 'rejected' WHERE id = ?", (coin_request_id,))
                conn.commit()
                await context.bot.send_message(
                    user_id,
                    LANGUAGES[lang]["coin_request_rejected"],
                    parse_mode="Markdown"
                )
                await query.message.reply_text(
                    f"❌ Coin request {coin_request_id} rejected for user {user_id}.",
                    parse_mode="Markdown"
                )
            else:
                await query.message.reply_text(
                    "❌ Coin request not found or already processed.",
                    parse_mode="Markdown"
                )
        finally:
            conn.close()
        await show_admin_panel(query.message, context, lang)

async def choose_payment(message, context: ContextTypes.DEFAULT_TYPE, lang: str):
    base_total = context.user_data.get("base_total", 0)
    delivery_fee = context.user_data.get("delivery_fee", 0)
    total = base_total + delivery_fee
    promo_code = context.user_data.get("promo_code")
    if promo_code and promo_code.lower() != "skip":
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT discount, usage_count, max_uses FROM promo_codes WHERE code = ?", (promo_code.upper(),))
            promo = c.fetchone()
            if promo and promo[1] < promo[2]:
                discount = float(promo[0]) / 100.0
                discounted_base_total = base_total * (1 - discount)
                total = discounted_base_total + delivery_fee
        except sqlite3.OperationalError as e:
            logger.error(f"Promo code table error: {e}")
            promo = None
        finally:
            conn.close()
        if not promo or promo[1] >= promo[2]:
            await delete_previous_message(context, message.chat_id)
            new_message = await message.reply_text(
                LANGUAGES[lang]["invalid_promo"],
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = new_message.message_id
            context.user_data["message_type"] = "alert"
            await show_cart(message, context, lang)
            return
    context.user_data["total_price"] = total
    keyboard = [
        [InlineKeyboardButton(LANGUAGES[lang]["coins"], callback_data="payment_coins")],
        [InlineKeyboardButton(LANGUAGES[lang]["cancel"], callback_data="main_menu")]
    ]
    await delete_previous_message(context, message.chat_id)
    new_message = await message.reply_text(
        LANGUAGES[lang]["choose_payment"] + f"\n💵 Total: {'{:.3f}'.format(total)} UZS (Delivery: {'{:.3f}'.format(delivery_fee)} UZS)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["last_message_id"] = new_message.message_id
    context.user_data["message_type"] = "button"

async def submit_order(query, context: ContextTypes.DEFAULT_TYPE, lang: str):
    user_id = query.from_user.id
    store_id = context.user_data.get("store_id", 1)
    cart = context.user_data.get("cart", {})
    delivery_time = context.user_data.get("delivery_time")
    payment_type = context.user_data.get("payment_type")
    promo_code = context.user_data.get("promo_code")
    location = context.user_data.get("location", {})
    base_total = context.user_data.get("base_total", 0)
    delivery_fee = context.user_data.get("delivery_fee", 0)
    total_price = context.user_data.get("total_price", base_total + delivery_fee)
    if not cart:
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["cart_empty"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        await show_main_menu(query.message, context, lang)
        return
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        product_ids = [str(pid) for pid in cart.keys()]
        c.execute("SELECT id, name, price FROM products WHERE id IN ({})".format(",".join("?" * len(product_ids))), product_ids)
        product_details = c.fetchall()
        c.execute("SELECT name, phone FROM users WHERE user_id = ?", (user_id,))
        user_info = c.fetchone()
        c.execute("SELECT name FROM stores WHERE id = ?", (store_id,))
        store_result = c.fetchone()
        store_name = store_result[0] if store_result else "Unknown Store"
        base_total = 0.0
        for p in product_details:
            product_id, _, price = p
            quantity = cart[str(product_id)]
            price = round(float(price), 3)
            base_total += round(price * quantity, 3)
        total_price = base_total + delivery_fee
        if promo_code and promo_code.lower() != "skip":
            c.execute("SELECT discount, usage_count, max_uses FROM promo_codes WHERE code = ?", (promo_code.upper(),))
            promo = c.fetchone()
            if promo and promo[1] < promo[2]:
                discount = float(promo[0]) / 100.0
                discounted_base_total = base_total * (1 - discount)
                total_price = discounted_base_total + delivery_fee
                c.execute("UPDATE promo_codes SET usage_count = usage_count + 1 WHERE code = ?", (promo_code.upper(),))
            else:
                await delete_previous_message(context, user_id)
                message = await query.message.reply_text(
                    LANGUAGES[lang]["invalid_promo"],
                    parse_mode="Markdown"
                )
                context.user_data["last_message_id"] = message.message_id
                context.user_data["message_type"] = "alert"
                await show_cart(query.message, context, lang)
                return
        if payment_type == "coins":
            c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
            coins = c.fetchone()[0]
            if coins < total_price:
                await delete_previous_message(context, user_id)
                message = await query.message.reply_text(
                    LANGUAGES[lang]["insufficient_coins"],
                    parse_mode="Markdown"
                )
                context.user_data["last_message_id"] = message.message_id
                context.user_data["message_type"] = "alert"
                await show_cart(query.message, context, lang)
                return
            c.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (total_price, user_id))
        product_list = ", ".join([f"{p[1]} x{cart[str(p[0])]} ({'{:.3f}'.format(round(float(p[2]) * cart[str(p[0])], 3))} UZS)" for p in product_details])
        c.execute("INSERT INTO orders (user_id, store_id, products, delivery_time, payment_type, status, promo_code, latitude, longitude, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (user_id, store_id, product_list, delivery_time, payment_type, "pending", promo_code,
                   location.get("latitude"), location.get("longitude"), datetime.now(UZBEKISTAN_TZ).strftime("%Y-%m-%d %H:%M:%S")))
        order_id = c.lastrowid
        conn.commit()
        context.user_data["cart"] = {}
        context.user_data["base_total"] = 0
        context.user_data["delivery_fee"] = 0
        context.user_data["total_price"] = 0
        order_details = LANGUAGES[lang]["order_details"].format(
            order_id=order_id,
            user_name=user_info[0],
            phone=user_info[1],
            store=store_name,
            products=product_list,
            payment=payment_type,
            delivery=delivery_time,
            total='{:.3f}'.format(total_price),
            delivery_fee='{:.3f}'.format(delivery_fee)
        )
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["order_submitted"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        for admin in ADMIN_ID:
            try:
                keyboard = [[InlineKeyboardButton(LANGUAGES[lang]["confirm_order"], callback_data=f"confirm_order_{order_id}")]]
                await context.bot.send_message(
                    admin,
                    order_details,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except TelegramError as e:
                logger.error(f"Failed to notify admin {admin}: {e}")
        await show_main_menu(query.message, context, lang)
    except sqlite3.OperationalError as e:
        logger.error(f"Database error during order submission: {e}")
        await delete_previous_message(context, user_id)
        message = await query.message.reply_text(
            LANGUAGES[lang]["error"].format(support=SUPPORT_USERNAME),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        await show_main_menu(query.message, context, lang)
    finally:
        conn.close()

# Show categories with pagination
async def show_categories(message, context: ContextTypes.DEFAULT_TYPE, lang: str, store_id: int):
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        c.execute("SELECT DISTINCT category FROM products WHERE store_id = ?", (store_id,))
        categories = [row[0] for row in c.fetchall()]
    finally:
        conn.close()
    category_offset = context.user_data.get("category_offset", 0)
    paginated_categories = categories[category_offset:category_offset + ITEMS_PER_BATCH]
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"category_{cat}")] for cat in paginated_categories]
    if len(categories) > category_offset + ITEMS_PER_BATCH:
        keyboard.append([InlineKeyboardButton(LANGUAGES[lang]["load_more"], callback_data="load_more_categories")])
    keyboard.append([InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data="main_menu")])
    await delete_previous_message(context, message.chat_id)
    new_message = await message.reply_text(
        LANGUAGES[lang]["choose_category"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["last_message_id"] = new_message.message_id
    context.user_data["message_type"] = "button"

# Show products with pagination
async def show_products(message, context: ContextTypes.DEFAULT_TYPE, lang: str):
    store_id = context.user_data.get("store_id", 1)
    category = context.user_data.get("category", "")
    product_offset = context.user_data.get("product_offset", 0)
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        c.execute("SELECT id, name, description, image, price FROM products WHERE store_id = ? AND category = ? LIMIT ? OFFSET ?",
                 (store_id, category, ITEMS_PER_BATCH, product_offset))
        products = c.fetchall()
        c.execute("SELECT COUNT(*) FROM products WHERE store_id = ? AND category = ?", (store_id, category))
        total_products = c.fetchone()[0]
    finally:
        conn.close()
    if not products:
        keyboard = [[InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"store_{store_id}")]]
        await delete_previous_message(context, message.chat_id)
        new_message = await message.reply_text(
            LANGUAGES[lang]["no_products"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = new_message.message_id
        context.user_data["message_type"] = "alert"
        return
    for product in products:
        product_id, name, description, image, price = product
        price = round(float(price), 3)
        keyboard = [
            [InlineKeyboardButton(LANGUAGES[lang]["add_to_cart"], callback_data=f"add_to_cart_{product_id}")],
            [InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"category_{category}")]
        ]
        if product_offset + ITEMS_PER_BATCH < total_products:
            keyboard.insert(1, [InlineKeyboardButton(LANGUAGES[lang]["load_more"], callback_data="load_more_products")])
        text = f"📦 *{name}*\n{description}\n💵 {'{:.3f}'.format(price)} UZS"
        await delete_previous_message(context, message.chat_id)
        if image:
            try:
                new_message = await message.reply_photo(
                    photo=image,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except TelegramError:
                new_message = await message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        else:
            new_message = await message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        context.user_data["last_message_id"] = new_message.message_id
        context.user_data["message_type"] = "button"
        await asyncio.sleep(0.5)

# Handle text and other inputs
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        lang = user[0] if user else context.user_data.get("language", "en")
    finally:
        conn.close()
    state = context.user_data.get("state", "")
    if state == "awaiting_name":
        context.user_data["name"] = text
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["enter_phone"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "awaiting_phone"
    elif state == "awaiting_phone":
        if not re.match(r"^\+998\d{9}$", text):
            await delete_previous_message(context, user_id)
            message = await update.message.reply_text(
                LANGUAGES[lang]["invalid_phone"],
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            return
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("INSERT INTO users (user_id, name, phone, language) VALUES (?, ?, ?, ?)",
                      (user_id, context.user_data["name"], text, context.user_data.get("language", "en")))
            conn.commit()
        finally:
            conn.close()
        context.user_data["state"] = ""
        await delete_previous_message(context, user_id)
        await show_main_menu(update.message, context, lang)
    elif state == "awaiting_new_name":
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("UPDATE users SET name = ? WHERE user_id = ?", (text, user_id))
            conn.commit()
        finally:
            conn.close()
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["change_name"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = ""
        await show_main_menu(update.message, context, lang)
    elif state == "awaiting_coin_amount":
        try:
            amount = float(text.replace(",", "."))
            if amount <= 0:
                raise ValueError
        except ValueError:
            await delete_previous_message(context, user_id)
            message = await update.message.reply_text(
                LANGUAGES[lang]["invalid_coin_amount"],
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            return
        context.user_data["coin_amount"] = amount
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["send_coin_check"].format(amount=amount),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "awaiting_coin_receipt"
    elif state == "awaiting_promo_code":
        context.user_data["promo_code"] = text
        keyboard = [
            [InlineKeyboardButton(LANGUAGES[lang]["next_slot"].format(time=get_next_delivery_slot()), callback_data="choose_delivery_next"),
             InlineKeyboardButton(LANGUAGES[lang]["admin_choose"], callback_data="choose_delivery_admin")],
            [InlineKeyboardButton(LANGUAGES[lang]["set_time_myself"], callback_data="choose_delivery_custom"),
             InlineKeyboardButton(LANGUAGES[lang]["cancel"], callback_data="main_menu")]
        ]
        await delete_previous_message(context, user_id)
        new_message = await update.message.reply_text(
            LANGUAGES[lang]["choose_delivery_time"],
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = new_message.message_id
        context.user_data["message_type"] = "button"
        context.user_data["state"] = ""
    elif state == "awaiting_custom_delivery_time":
        delivery_time, error = parse_delivery_time(text, lang)
        if error:
            await delete_previous_message(context, user_id)
            message = await update.message.reply_text(
                error,
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            return
        context.user_data["delivery_time"] = delivery_time
        await choose_payment(update.message, context, lang)
        context.user_data["state"] = ""
    elif state == "awaiting_feedback":
        try:
            rating = int(text)
            if 1 <= rating <= 5:
                await delete_previous_message(context, user_id)
                message = await update.message.reply_text(
                    f"🌟 Thank you for your {rating} rating!",
                    parse_mode="Markdown"
                )
                context.user_data["last_message_id"] = message.message_id
                context.user_data["message_type"] = "alert"
                context.user_data["state"] = ""
                await show_main_menu(update.message, context, lang)
            else:
                raise ValueError
        except ValueError:
            await delete_previous_message(context, user_id)
            message = await update.message.reply_text(
                LANGUAGES[lang]["invalid_feedback"],
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
    elif state == "admin_awaiting_product_name":
        context.user_data["product_name"] = text
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["enter_product_desc"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "admin_awaiting_product_desc"
    elif state == "admin_awaiting_product_desc":
        context.user_data["product_desc"] = text
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["enter_product_price"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "admin_awaiting_product_price"
    elif state == "admin_awaiting_product_price":
        try:
            price = float(text.replace(",", "."))
            if price <= 0:
                raise ValueError
        except ValueError:
            await delete_previous_message(context, user_id)
            message = await update.message.reply_text(
                "❌ Invalid price. Please enter a positive number.",
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            return
        context.user_data["product_price"] = price
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["enter_product_category"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "admin_awaiting_product_category"
    elif state == "admin_awaiting_product_category":
        context.user_data["product_category"] = text
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["upload_product_image"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "admin_awaiting_product_image"
    elif state == "admin_awaiting_promo_code":
        context.user_data["promo_code"] = text.upper()
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["enter_promo_discount"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "admin_awaiting_promo_discount"
    elif state == "admin_awaiting_promo_discount":
        try:
            discount = float(text)
            if not 1 <= discount <= 100:
                raise ValueError
        except ValueError:
            await delete_previous_message(context, user_id)
            message = await update.message.reply_text(
                "❌ Invalid discount. Please enter a percentage between 1 and 100.",
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            return
        context.user_data["promo_discount"] = discount
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["enter_promo_max_uses"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = "admin_awaiting_promo_max_uses"
    elif state == "admin_awaiting_promo_max_uses":
        try:
            max_uses = int(text)
            if max_uses <= 0:
                raise ValueError
        except ValueError:
            await delete_previous_message(context, user_id)
            message = await update.message.reply_text(
                "❌ Invalid number. Please enter a positive integer.",
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            return
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("INSERT INTO promo_codes (code, discount, max_uses) VALUES (?, ?, ?)",
                      (context.user_data["promo_code"], context.user_data["promo_discount"], max_uses))
            conn.commit()
        except sqlite3.IntegrityError:
            await delete_previous_message(context, user_id)
            message = await update.message.reply_text(
                "❌ Promo code already exists.",
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            context.user_data["state"] = ""
            await show_admin_panel(update.message, context, lang)
            return
        finally:
            conn.close()
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["promo_added"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = ""
        await show_admin_panel(update.message, context, lang)
    elif state == "awaiting_search_query":
        query = text.lower()
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("SELECT id, name, description, image, price FROM products WHERE store_id = ? AND (LOWER(name) LIKE ? OR LOWER(description) LIKE ?)",
                     (context.user_data.get("store_id", 1), f"%{query}%", f"%{query}%"))
            products = c.fetchall()
        finally:
            conn.close()
        if not products:
            keyboard = [[InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"store_{context.user_data.get('store_id', 1)}")]]
            await delete_previous_message(context, user_id)
            message = await update.message.reply_text(
                LANGUAGES[lang]["no_products"],
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            context.user_data["last_message_id"] = message.message_id
            context.user_data["message_type"] = "alert"
            context.user_data["state"] = ""
            return
        for product in products:
            product_id, name, description, image, price = product
            price = round(float(price), 3)
            keyboard = [
                [InlineKeyboardButton(LANGUAGES[lang]["add_to_cart"], callback_data=f"add_to_cart_{product_id}")],
                [InlineKeyboardButton(LANGUAGES[lang]["go_back"], callback_data=f"store_{context.user_data.get('store_id', 1)}")]
            ]
            text = f"📦 *{name}*\n{description}\n💵 {'{:.3f}'.format(price)} UZS"
            await delete_previous_message(context, user_id)
            if image:
                try:
                    new_message = await update.message.reply_photo(
                        photo=image,
                        caption=text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown"
                    )
                except TelegramError:
                    new_message = await update.message.reply_text(
                        text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode="Markdown"
                    )
            else:
                new_message = await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            context.user_data["last_message_id"] = new_message.message_id
            context.user_data["message_type"] = "button"
            await asyncio.sleep(0.5)
        context.user_data["state"] = ""

# Handle location
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        lang = user[0] if user else context.user_data.get("language", "en")
    finally:
        conn.close()
    location = update.message.location
    context.user_data["location"] = {"latitude": location.latitude, "longitude": location.longitude}
    keyboard = [
        [InlineKeyboardButton("ЦУМ", callback_data="store_1"),
         InlineKeyboardButton("Sergeli", callback_data="store_2")]
    ]
    await delete_previous_message(context, user_id)
    new_message = await update.message.reply_text(
        LANGUAGES[lang]["choose_store"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["last_message_id"] = new_message.message_id
    context.user_data["message_type"] = "button"
    context.user_data["state"] = ""

# Handle photo (for product image or coin receipt)
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = context.user_data.get("state", "")
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        lang = user[0] if user else context.user_data.get("language", "en")
    finally:
        conn.close()
    if state == "admin_awaiting_product_image":
        photo = update.message.photo[-1]
        file_id = photo.file_id
        store_id = context.user_data.get("admin_store_id", 1)
        product_data = {
            "id": None,
            "name": context.user_data["product_name"],
            "description": context.user_data["product_desc"],
            "image": file_id,
            "price": context.user_data["product_price"],
            "category": context.user_data["product_category"],
            "store_id": store_id
        }
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("INSERT INTO products (name, description, image, price, category, store_id) VALUES (?, ?, ?, ?, ?, ?)",
                      (product_data["name"], product_data["description"], product_data["image"],
                       product_data["price"], product_data["category"], product_data["store_id"]))
            product_data["id"] = c.lastrowid
            conn.commit()
        finally:
            conn.close()
        log_product_to_file(product_data)
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["product_added"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = ""
        await show_admin_panel(update.message, context, lang)
    elif state == "awaiting_coin_receipt":
        photo = update.message.photo[-1]
        file_id = photo.file_id
        amount = context.user_data.get("coin_amount", 0)
        conn = sqlite3.connect("store_bot.db")
        try:
            c = conn.cursor()
            c.execute("INSERT INTO coin_requests (user_id, amount, status, receipt_file_id, created_at) VALUES (?, ?, ?, ?, ?)",
                      (user_id, amount, "pending", file_id, datetime.now(UZBEKISTAN_TZ).strftime("%Y-%m-%d %H:%M:%S")))
            coin_request_id = c.lastrowid
            conn.commit()
        finally:
            conn.close()
        await delete_previous_message(context, user_id)
        message = await update.message.reply_text(
            LANGUAGES[lang]["coin_request_sent"],
            parse_mode="Markdown"
        )
        context.user_data["last_message_id"] = message.message_id
        context.user_data["message_type"] = "alert"
        context.user_data["state"] = ""
        for admin in ADMIN_ID:
            try:
                keyboard = [
                    [InlineKeyboardButton("✅ Approve", callback_data=f"approve_coin_{coin_request_id}"),
                     InlineKeyboardButton("❌ Reject", callback_data=f"reject_coin_{coin_request_id}")]
                ]
                await context.bot.send_photo(
                    admin,
                    photo=file_id,
                    caption=f"🧾 Coin request from user {user_id} for {'{:.3f}'.format(amount)} coins.",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except TelegramError as e:
                logger.error(f"Failed to notify admin {admin}: {e}")
        await show_main_menu(update.message, context, lang)

# Scheduler for admin response timeout
async def check_admin_timeout(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("store_bot.db")
    try:
        c = conn.cursor()
        timeout_threshold = datetime.now(UZBEKISTAN_TZ) - timedelta(minutes=ADMIN_RESPONSE_TIMEOUT)
        c.execute("SELECT order_id, user_id FROM orders WHERE status = 'pending' AND created_at <= ?",
                  (timeout_threshold.strftime("%Y-%m-%d %H:%M:%S"),))
        pending_orders = c.fetchall()
        for order_id, user_id in pending_orders:
            c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
            user = c.fetchone()
            lang = user[0] if user else "en"
            try:
                await context.bot.send_message(
                    user_id,
                    LANGUAGES[lang]["order_confirmed"].format(time=context.user_data.get("delivery_time", "Admin will choose")),
                    parse_mode="Markdown"
                )
                c.execute("UPDATE orders SET status = 'confirmed' WHERE order_id = ?", (order_id,))
                conn.commit()
            except TelegramError as e:
                logger.error(f"Failed to notify user {user_id} for order {order_id}: {e}")
    finally:
        conn.close()

# Main function
def main():
    init_db()
    app = Application.builder().token(API_TOKEN).build()
    scheduler = AsyncIOScheduler(timezone=UZBEKISTAN_TZ)
    scheduler.add_job(check_admin_timeout, "interval", minutes=5, args=[app])
    scheduler.start()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_error_handler(error_handler)
    app.run_polling()

if __name__ == "__main__":
    main()