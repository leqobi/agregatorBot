import asyncio
import os
import threading
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import executor
from flask import Flask

API_TOKEN = 'ТВОЙ_ТОКЕН'
ADMIN_ID = 8515021528  # твой Telegram ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Статистика
users = set()  # все пользователи, кто запустил бота
clicks = {  # счётчики кликов по категориям
    'vpn': 0,
    'earn': 0,
    'services': 0,
    'other': 0
}

# Связь с создателем
waiting_for_support = set()   # юзеры, которые сейчас пишут сообщение создателю
last_user_for_admin = {}      # {ADMIN_ID: user_id} — кому админ ответит, если напишет без /reply

# ------------------- Клавиатуры -------------------
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔒 VPN", callback_data="vpn"),
        InlineKeyboardButton("💰 Заработок", callback_data="earn"),
        InlineKeyboardButton("🛠 Сервисы", callback_data="services"),
        InlineKeyboardButton("📦 Разное", callback_data="other")
    )
    keyboard.add(InlineKeyboardButton("📞 Написать создателю", callback_data="support"))
    return keyboard

def get_back_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("◀️ Назад в меню", callback_data="main_menu"))
    return keyboard

# ------------------- Команды -------------------
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    users.add(user_id)  # запоминаем пользователя
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"Привет, {name}! 👋\nЯ бот-агрегатор. Выбери категорию:",
        reply_markup=get_main_keyboard()
    )

@dp.message_handler(commands=['stats'])
async def stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Только для админа.")
        return
    total_users = len(users)
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🔒 VPN: {clicks['vpn']} кликов\n"
        f"💰 Заработок: {clicks['earn']} кликов\n"
        f"🛠 Сервисы: {clicks['services']} кликов\n"
        f"📦 Разное: {clicks['other']} кликов"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message_handler(commands=['broadcast'])
async def broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Только для админа.")
        return
    text = message.get_args()
    if not text:
        await message.answer("❌ Напиши текст после команды, например:\n/broadcast Всем привет!")
        return
    if not users:
        await message.answer("❌ Нет пользователей для рассылки.")
        return
    sent = 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.05)  # чтобы не превысить лимиты
        except:
            pass
    await message.answer(f"✅ Рассылка завершена. Отправлено {sent} пользователям.")

@dp.message_handler(commands=['reply'])
async def reply_to_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Только для админа.")
        return
    args = message.get_args().split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Используй: /reply ID_пользователя Текст ответа")
        return
    user_id_str, reply_text = args
    try:
        user_id = int(user_id_str)
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    try:
        await bot.send_message(user_id, f"📨 <b>Ответ от создателя:</b>\n{reply_text}", parse_mode="HTML")
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {str(e)}")

# ------------------- Связь с создателем -------------------
@dp.callback_query_handler(lambda c: c.data == 'support')
async def support_request(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    waiting_for_support.add(user_id)
    await callback.message.edit_text(
        "📝 Напиши своё сообщение для создателя (вопрос, отзыв или предложение).\n\n"
        "Я перешлю его создателю, а он ответит тебе прямо в этом чате.",
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

# ------------------- Обработка текстовых сообщений -------------------
@dp.message_handler(content_types=['text'])
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # Сообщения от самого админа не трогаем (команды обрабатываются отдельно)
    if user_id == ADMIN_ID:
        return

    # Если пользователь сейчас пишет сообщение создателю
    if user_id in waiting_for_support:
        waiting_for_support.remove(user_id)
        last_user_for_admin[ADMIN_ID] = user_id
        name = message.from_user.full_name or message.from_user.first_name
        username = f"@{message.from_user.username}" if message.from_user.username else "без юзернейма"
        await bot.send_message(
            ADMIN_ID,
            f"📩 <b>Новое сообщение от пользователя</b>\n"
            f"От: {name} ({username})\n"
            f"ID: <code>{user_id}</code>\n"
            f"Текст: {text}\n\n"
            f"💬 Ответь командой: /reply {user_id} твой_ответ",
            parse_mode="HTML"
        )
        await message.answer("✅ Сообщение отправлено создателю. Ожидай ответа здесь же.")

# ------------------- Обработчики кнопок -------------------
@dp.callback_query_handler(lambda c: c.data == 'main_menu')
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("Выбери категорию:", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == 'vpn')
async def vpn(callback: types.CallbackQuery):
    clicks['vpn'] += 1
    text = (
        "🔒 <b>VPN и доступ</b>\n\n"
        "• <a href=\"https://t.me/chunkyvpn_bot?start=9a25d420\">ChunkyVPN</a>\n"
        "• <a href=\"https://t.me/colavpnbot?start=ref5683031732\">COLAVPN</a>\n"
        "• <a href=\"https://t.me/allvpn?start=refbNndYvkv\">ALL VPN</a>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard(), disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == 'earn')
async def earn(callback: types.CallbackQuery):
    clicks['earn'] += 1
    text = (
        "💰 <b>Заработок и NFT</b>\n\n"
        "• <a href=\"https://t.me/Agent301Bot/app?startapp=ref_ALJ7Cn\">Agent 301</a>\n"
        "  — получай коллекционные подарки Telegram за активность\n"
        "• <a href=\"https://t.me/EasyGiftDropbot?startapp=ref_983985\">Easy Gift</a>\n"
        "  — испытай удачу и забирай подарки за звёзды"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard(), disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == 'services')
async def services(callback: types.CallbackQuery):
    clicks['services'] += 1
    text = (
        "🛠 <b>Полезные сервисы</b>\n\n"
        "• <a href=\"https://t.me/meri_sh0p_bot?start=7587603870\">MERI SHOP</a>\n"
        "  — магазин номеров для Telegram\n"
        "• <a href=\"https://t.me/Dark_Gpt1_bot?start=cb6e6f1100b443edaf1f79148f339103\">Dark_Gpt1_bot</a>\n"
        "  — GPT без цензуры и запретов\n"
        "• <a href=\"https://t.me/ShopAethelBot?start=ref_7587603870\">ShopAethelBot</a>\n"
        "  — магазин подписок на разные сервисы\n"
        "• <a href=\"https://t.me/MogGramBot?start=ref8515021528\">MogGram</a>\n"
        "  — автоматизация чатов"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard(), disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == 'other')
async def other(callback: types.CallbackQuery):
    clicks['other'] += 1
    text = (
        "📦 <b>Разное</b>\n\n"
        "• <a href=\"https://t.me/BanksStars2bot?start=ref_5683031732\">BanksStars2bot</a>\n"
        "  — аренда подарков\n"
        "• <a href=\"https://t.me/SafeCallerBot?start=HKZ49sUj\">SafeCallerBot</a>\n"
        "  — безопасная связь"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_back_keyboard(), disable_web_page_preview=True)
    await callback.answer()

# ------------------- Flask сервер (нужен Render, чтобы видеть открытый порт) -------------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ------------------- Запуск -------------------
if __name__ == '__main__':
    # Flask в отдельном потоке — держит порт открытым для Render
    threading.Thread(target=run_flask, daemon=True).start()

    # Бот в основном потоке
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    executor.start_polling(dp, skip_updates=True, loop=loop)
