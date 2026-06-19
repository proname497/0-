# pip install aiogram==2.25.1 telethon pytesseract Pillow qrcode[pil] googletrans==4.0.0-rc1 requests aiohttp==3.8.6

import asyncio
import os
import re
import random
import string
import tempfile
import hashlib
import base64
import requests
from datetime import datetime, timedelta
from urllib.parse import quote, unquote
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
import qrcode
import pytesseract
from PIL import Image, ImageFilter
from googletrans import Translator

BOT_TOKEN = '8805526086:AAHcH8kjX7FXuBgkut5dVMf2RCB0C1gp3Jo'
API_ID = 32828349
API_HASH = 'afe8886d04de4ca37c61fb34f2667806'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
translator = Translator()
auth_data = {}
user_sessions = {}

MORSE_RU = {'А': '.-', 'Б': '-...', 'В': '.--', 'Г': '--.', 'Д': '-..', 'Е': '.', 'Ж': '...-', 'З': '--..', 'И': '..', 'Й': '.---', 'К': '-.-', 'Л': '.-..', 'М': '--', 'Н': '-.', 'О': '---', 'П': '.--.', 'Р': '.-.', 'С': '...', 'Т': '-', 'У': '..-', 'Ф': '..-.', 'Х': '....', 'Ц': '-.-.', 'Ч': '---.', 'Ш': '----', 'Щ': '--.-', 'Ъ': '--.--', 'Ы': '-.--', 'Ь': '-..-', 'Э': '..-..', 'Ю': '..--', 'Я': '.-.-'}
MORSE_EN = {'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--', 'Z': '--..'}
MORSE = {**MORSE_RU, **MORSE_EN, '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.', ' ': '/'}
MORSE_REVERSE = {v: k for k, v in MORSE.items()}

class AuthStates(StatesGroup):
    waiting_phone = State()
    entering_code = State()
    waiting_password = State()

def get_code_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton("1", callback_data="code_1"), InlineKeyboardButton("2", callback_data="code_2"), InlineKeyboardButton("3", callback_data="code_3"),
        InlineKeyboardButton("4", callback_data="code_4"), InlineKeyboardButton("5", callback_data="code_5"), InlineKeyboardButton("6", callback_data="code_6"),
        InlineKeyboardButton("7", callback_data="code_7"), InlineKeyboardButton("8", callback_data="code_8"), InlineKeyboardButton("9", callback_data="code_9"),
        InlineKeyboardButton("◀️", callback_data="code_del"), InlineKeyboardButton("0", callback_data="code_0"), InlineKeyboardButton("✅", callback_data="code_ok"),
    ]
    keyboard.add(*buttons)
    return keyboard

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("📱 Поделиться номером", request_contact=True))
    keyboard.add(KeyboardButton("❓ Помощь"), KeyboardButton("👤 Авторы"))
    return keyboard

BETA_MSG = "⚠️ Недоступно в бета-версии"

async def create_userbot(phone, user_id, session_client=None):
    if session_client:
        client = session_client
    else:
        client = TelegramClient(f'session_{user_id}', API_ID, API_HASH)
        await client.start(phone=phone)
    
    user_sessions[user_id] = client

    # 📨 РАССЫЛКА
    @client.on(events.NewMessage(pattern=r'\.broadcast (.+)', from_users=user_id))
    async def broadcast(event):
        await event.delete()
        text = event.pattern_match.group(1)
        sent, failed = 0, 0
        msg = await event.respond("📤 Рассылка...")
        async for dialog in client.iter_dialogs():
            if dialog.is_user and not dialog.entity.bot:
                try:
                    await client.send_message(dialog.entity, text)
                    sent += 1
                    await asyncio.sleep(1)
                except:
                    failed += 1
        await msg.edit(f"Отправлено: {sent} | Ошибок: {failed}")

    @client.on(events.NewMessage(pattern=r'\.bc (.+)', from_users=user_id))
    async def bc_group(event):
        await event.delete()
        text = event.pattern_match.group(1)
        sent = 0
        msg = await event.respond("📤 Рассылка по группам...")
        async for dialog in client.iter_dialogs():
            if dialog.is_group:
                try:
                    await client.send_message(dialog.entity, text)
                    sent += 1
                    await asyncio.sleep(1)
                except:
                    pass
        await msg.edit(f"Отправлено в групп: {sent}")

    @client.on(events.NewMessage(pattern=r'\.bclist', from_users=user_id))
    async def bclist(event):
        await event.delete()
        groups = []
        async for dialog in client.iter_dialogs():
            if dialog.is_group:
                groups.append(dialog.name)
        await event.respond("\n".join(groups[:20]) if groups else "Нет групп")

    @client.on(events.NewMessage(pattern=r'\.delay (\d+)', from_users=user_id))
    async def delay(event):
        await event.delete()
        await event.respond(f"Задержка: {event.pattern_match.group(1)} сек")

    @client.on(events.NewMessage(pattern=r'\.stopbc', from_users=user_id))
    async def stopbc(event):
        await event.delete()
        await event.respond("Рассылка остановлена")

    # 👥 КОНТАКТЫ
    @client.on(events.NewMessage(pattern=r'\.ghosts', from_users=user_id))
    async def ghosts(event):
        await event.delete()
        ghosts_list = []
        contacts = await client.get_contacts()
        for contact in contacts:
            if not contact.mutual_contact and contact.contact:
                name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                username = f"@{contact.username}" if contact.username else "нет"
                ghosts_list.append(f"{name} - {username}")
        await event.respond("\n".join(ghosts_list[:30]) if ghosts_list else "Никто не удалял")

    @client.on(events.NewMessage(pattern=r'\.mutual', from_users=user_id))
    async def mutual(event):
        await event.delete()
        mutual_list = []
        contacts = await client.get_contacts()
        for contact in contacts:
            if contact.mutual_contact:
                name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                mutual_list.append(name)
        await event.respond("\n".join(mutual_list[:30]) if mutual_list else "Нет взаимных контактов")

    @client.on(events.NewMessage(pattern=r'\.nocontact', from_users=user_id))
    async def nocontact(event):
        await event.delete()
        no_list = []
        async for dialog in client.iter_dialogs():
            if dialog.is_user and not dialog.entity.bot and not dialog.entity.contact:
                name = f"{dialog.entity.first_name or ''} {dialog.entity.last_name or ''}".strip()
                no_list.append(name)
        await event.respond("\n".join(no_list[:20]) if no_list else "Все в контактах")

    @client.on(events.NewMessage(pattern=r'\.search (.+)', from_users=user_id))
    async def search(event):
        await event.delete()
        query = event.pattern_match.group(1).lower()
        found = []
        async for dialog in client.iter_dialogs():
            name = f"{dialog.entity.first_name or ''} {dialog.entity.last_name or ''} {dialog.entity.username or ''}".lower()
            if query in name:
                found.append(dialog.name)
        await event.respond("\n".join(found[:10]) if found else "Не найдено")

    @client.on(events.NewMessage(pattern=r'\.export', from_users=user_id))
    async def export(event):
        await event.delete()
        contacts = await client.get_contacts()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for c in contacts:
                name = f"{c.first_name or ''} {c.last_name or ''}".strip()
                phone = c.phone or 'нет'
                username = f"@{c.username}" if c.username else 'нет'
                f.write(f"{name} | {phone} | {username}\n")
            await client.send_file(event.chat_id, f.name)
            os.unlink(f.name)

    # 🎵 МУЗЫКА
    @client.on(events.NewMessage(pattern=r'\.song (.+)', from_users=user_id))
    async def song(event):
        await event.delete()
        query = event.pattern_match.group(1)
        try:
            r = requests.get(f'https://itunes.apple.com/search?term={query}&limit=5&media=music')
            data = r.json()
            if data['resultCount'] > 0:
                result = "\n".join([f"{i+1}. {t['artistName']} - {t['trackName']}" for i, t in enumerate(data['results'][:5])])
                result += "\n\nОтправь .dl 1 чтобы скачать"
                await event.respond(result)
            else:
                await event.respond("Не найдено")
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.dl (\d+)', from_users=user_id))
    async def dl_song(event):
        await event.delete()
        await event.respond(BETA_MSG)

    # 📸 ФОТО
    @client.on(events.NewMessage(pattern=r'\.ocr', from_users=user_id))
    async def ocr(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на фото")
            return
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.respond("Это не фото")
            return
        try:
            photo = await reply.download_media()
            img = Image.open(photo).convert('L').filter(ImageFilter.SHARPEN)
            text = pytesseract.image_to_string(img, lang='rus+eng')
            await event.respond(text if text.strip() else "Текст не найден")
            os.remove(photo)
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.enhance', from_users=user_id))
    async def enhance(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на фото")
            return
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.respond("Это не фото")
            return
        try:
            photo = await reply.download_media()
            img = Image.open(photo).filter(ImageFilter.SHARPEN)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                img.save(f.name)
                await client.send_file(event.chat_id, f.name)
                os.unlink(f.name)
            os.remove(photo)
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.bw', from_users=user_id))
    async def bw(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на фото")
            return
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.respond("Это не фото")
            return
        try:
            photo = await reply.download_media()
            img = Image.open(photo).convert('L')
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                img.save(f.name)
                await client.send_file(event.chat_id, f.name)
                os.unlink(f.name)
            os.remove(photo)
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.blur', from_users=user_id))
    async def blur(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на фото")
            return
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.respond("Это не фото")
            return
        try:
            photo = await reply.download_media()
            img = Image.open(photo).filter(ImageFilter.GaussianBlur(10))
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                img.save(f.name)
                await client.send_file(event.chat_id, f.name)
                os.unlink(f.name)
            os.remove(photo)
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.compress', from_users=user_id))
    async def compress(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на фото")
            return
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.respond("Это не фото")
            return
        try:
            photo = await reply.download_media()
            img = Image.open(photo)
            img.save(photo, quality=30)
            await client.send_file(event.chat_id, photo)
            os.remove(photo)
        except:
            await event.respond(BETA_MSG)

    # 🛠 ИНСТРУМЕНТЫ
    @client.on(events.NewMessage(pattern=r'\.calc (.+)', from_users=user_id))
    async def calc(event):
        await event.delete()
        try:
            expr = re.sub(r'[^0-9+\-*/().%^**\s]', '', event.pattern_match.group(1))
            await event.respond(str(eval(expr)))
        except:
            await event.respond("Ошибка в выражении")

    @client.on(events.NewMessage(pattern=r'\.(usd|eur|rub|cny) (\d+\.?\d*)', from_users=user_id))
    async def currency(event):
        await event.delete()
        curr, amount = event.pattern_match.group(1), float(event.pattern_match.group(2))
        try:
            r = requests.get('https://api.exchangerate-api.com/v4/latest/USD')
            data = r.json()
            rates = data['rates']
            if curr == 'usd':
                await event.respond(f"{amount * rates['RUB']:.2f} RUB")
            elif curr == 'eur':
                await event.respond(f"{amount * (rates['RUB'] / rates['EUR']):.2f} RUB")
            elif curr == 'rub':
                await event.respond(f"{amount / rates['RUB']:.2f} USD")
            elif curr == 'cny':
                await event.respond(f"{amount * (rates['RUB'] / rates['CNY']):.2f} RUB")
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.tr (\w+) (.+)', from_users=user_id))
    async def translate_cmd(event):
        await event.delete()
        try:
            dest = event.pattern_match.group(1)
            text = event.pattern_match.group(2)
            result = translator.translate(text, dest=dest)
            await event.respond(result.text)
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.weather (.+)', from_users=user_id))
    async def weather(event):
        await event.delete()
        try:
            city = event.pattern_match.group(1)
            r = requests.get(f'https://wttr.in/{city}?format=%l:+%t+%C+%h&lang=ru')
            await event.respond(r.text)
        except:
            await event.respond("Город не найден")

    @client.on(events.NewMessage(pattern=r'\.qr (.+)', from_users=user_id))
    async def qr_gen(event):
        await event.delete()
        try:
            text = event.pattern_match.group(1)
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                img.save(f.name)
                await client.send_file(event.chat_id, f.name)
                os.unlink(f.name)
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.morse (.+)', from_users=user_id))
    async def morse_encode(event):
        await event.delete()
        text = event.pattern_match.group(1).upper()
        result = ' '.join(MORSE.get(c, '?') for c in text)
        await event.respond(result)

    @client.on(events.NewMessage(pattern=r'\.unmorse (.+)', from_users=user_id))
    async def morse_decode(event):
        await event.delete()
        try:
            code = event.pattern_match.group(1)
            result = ''.join(MORSE_REVERSE.get(c, '?') for c in code.split())
            await event.respond(result)
        except:
            await event.respond("Неверный код Морзе")

    @client.on(events.NewMessage(pattern=r'\.pass(?: (\d+))?', from_users=user_id))
    async def password_gen(event):
        await event.delete()
        length = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else 16
        chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
        password = ''.join(random.choice(chars) for _ in range(length))
        await event.respond(password)

    @client.on(events.NewMessage(pattern=r'\.ip(?: (.+))?', from_users=user_id))
    async def ip_info(event):
        await event.delete()
        try:
            ip = event.pattern_match.group(1)
            url = f'http://ip-api.com/json/{ip}?fields=query,country,city,isp' if ip else 'http://ip-api.com/json/?fields=query,country,city,isp'
            r = requests.get(url)
            data = r.json()
            await event.respond(f"{data['query']}\n{data['country']}\n{data['city']}\n{data['isp']}")
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.time (.+)', from_users=user_id))
    async def time_cmd(event):
        await event.delete()
        await event.respond(datetime.now().strftime('%H:%M:%S'))

    @client.on(events.NewMessage(pattern=r'\.dict (.+)', from_users=user_id))
    async def dict_cmd(event):
        await event.delete()
        try:
            word = event.pattern_match.group(1)
            r = requests.get(f'https://api.dictionaryapi.dev/api/v2/entries/en/{word}')
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                defs = data[0]['meanings'][0]['definitions'][0]['definition']
                await event.respond(defs)
            else:
                await event.respond("Не найдено")
        except:
            await event.respond(BETA_MSG)

    # 💎 КРИПТА
    @client.on(events.NewMessage(pattern=r'\.(btc|eth|bnb|sol|doge)', from_users=user_id))
    async def crypto(event):
        await event.delete()
        try:
            symbol = event.pattern_match.group(1).upper()
            r = requests.get(f'https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT')
            price = float(r.json()['price'])
            await event.respond(f"${price:,.2f}")
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.top10', from_users=user_id))
    async def top10(event):
        await event.delete()
        try:
            r = requests.get('https://api.binance.com/api/v3/ticker/24hr')
            data = r.json()
            usdt = [x for x in data if x['symbol'].endswith('USDT')]
            top = sorted(usdt, key=lambda x: float(x['quoteVolume']), reverse=True)[:10]
            result = "\n".join([f"{i+1}. {t['symbol'][:-4]}: ${float(t['lastPrice']):,.2f}" for i, t in enumerate(top)])
            await event.respond(result)
        except:
            await event.respond(BETA_MSG)

    # 🧹 ОЧИСТКА
    @client.on(events.NewMessage(pattern=r'\.clean$', from_users=user_id))
    async def clean(event):
        await event.delete()
        deleted = 0
        async for message in client.iter_messages(event.chat_id, from_user='me', limit=100):
            try:
                await message.delete()
                deleted += 1
                await asyncio.sleep(0.5)
            except:
                pass
        await event.respond(f"Удалено: {deleted}")

    @client.on(events.NewMessage(pattern=r'\.clean (\d+)', from_users=user_id))
    async def clean_n(event):
        await event.delete()
        try:
            n = int(event.pattern_match.group(1))
            deleted = 0
            async for message in client.iter_messages(event.chat_id, from_user='me', limit=n):
                try:
                    await message.delete()
                    deleted += 1
                    await asyncio.sleep(0.3)
                except:
                    pass
            await event.respond(f"Удалено: {deleted}")
        except:
            await event.respond("Ошибка")

    # 🎮 РАЗВЛЕЧЕНИЯ
    @client.on(events.NewMessage(pattern=r'\.dice', from_users=user_id))
    async def dice(event):
        await event.delete()
        await event.respond(str(random.randint(1, 6)))

    @client.on(events.NewMessage(pattern=r'\.yesno', from_users=user_id))
    async def yesno(event):
        await event.delete()
        await event.respond(random.choice(["Да", "Нет", "Возможно", "Спроси позже", "100%"]))

    @client.on(events.NewMessage(pattern=r'\.choose (.+)', from_users=user_id))
    async def choose(event):
        await event.delete()
        options = [x.strip() for x in event.pattern_match.group(1).split(',')]
        await event.respond(random.choice(options))

    @client.on(events.NewMessage(pattern=r'\.riddle', from_users=user_id))
    async def riddle(event):
        await event.delete()
        riddles = [("Зимой и летом одним цветом", "Ёлка"), ("Висит груша — нельзя скушать", "Лампочка")]
        r = random.choice(riddles)
        await event.respond(f"{r[0]}\n\nОтвет: {r[1]}")

    # 🔐 КОДИРОВАНИЕ
    @client.on(events.NewMessage(pattern=r'\.b64enc (.+)', from_users=user_id))
    async def b64enc(event):
        await event.delete()
        await event.respond(base64.b64encode(event.pattern_match.group(1).encode()).decode())

    @client.on(events.NewMessage(pattern=r'\.b64dec (.+)', from_users=user_id))
    async def b64dec(event):
        await event.delete()
        try:
            await event.respond(base64.b64decode(event.pattern_match.group(1)).decode())
        except:
            await event.respond("Ошибка декодирования")

    @client.on(events.NewMessage(pattern=r'\.md5 (.+)', from_users=user_id))
    async def md5(event):
        await event.delete()
        await event.respond(hashlib.md5(event.pattern_match.group(1).encode()).hexdigest())

    @client.on(events.NewMessage(pattern=r'\.sha256 (.+)', from_users=user_id))
    async def sha256(event):
        await event.delete()
        await event.respond(hashlib.sha256(event.pattern_match.group(1).encode()).hexdigest())

    @client.on(events.NewMessage(pattern=r'\.hashid (.+)', from_users=user_id))
    async def hashid(event):
        await event.delete()
        h = event.pattern_match.group(1)
        types = []
        if len(h) == 32: types.append("MD5")
        if len(h) == 64: types.append("SHA256")
        if len(h) == 40: types.append("SHA1")
        await event.respond(", ".join(types) if types else "Неизвестно")

    @client.on(events.NewMessage(pattern=r'\.rot13 (.+)', from_users=user_id))
    async def rot13(event):
        await event.delete()
        text = event.pattern_match.group(1)
        result = ''.join([chr((ord(c) - 65 + 13) % 26 + 65) if c.isupper() else chr((ord(c) - 97 + 13) % 26 + 97) if c.islower() else c for c in text])
        await event.respond(result)

    @client.on(events.NewMessage(pattern=r'\.hex (.+)', from_users=user_id))
    async def hex_encode(event):
        await event.delete()
        await event.respond(event.pattern_match.group(1).encode().hex())

    @client.on(events.NewMessage(pattern=r'\.urlenc (.+)', from_users=user_id))
    async def urlenc(event):
        await event.delete()
        await event.respond(quote(event.pattern_match.group(1)))

    @client.on(events.NewMessage(pattern=r'\.urldec (.+)', from_users=user_id))
    async def urldec(event):
        await event.delete()
        await event.respond(unquote(event.pattern_match.group(1)))

    # 👤 АККАУНТ
    @client.on(events.NewMessage(pattern=r'\.bio (.+)', from_users=user_id))
    async def bio(event):
        await event.delete()
        try:
            await client(UpdateProfileRequest(about=event.pattern_match.group(1)))
            await event.respond("Био обновлено")
        except:
            await event.respond("Ошибка")

    @client.on(events.NewMessage(pattern=r'\.name (.+)', from_users=user_id))
    async def name(event):
        await event.delete()
        try:
            await client(UpdateProfileRequest(first_name=event.pattern_match.group(1)))
            await event.respond("Имя обновлено")
        except:
            await event.respond("Ошибка")

    @client.on(events.NewMessage(pattern=r'\.lastname (.+)', from_users=user_id))
    async def lastname(event):
        await event.delete()
        try:
            await client(UpdateProfileRequest(last_name=event.pattern_match.group(1)))
            await event.respond("Фамилия обновлена")
        except:
            await event.respond("Ошибка")

    @client.on(events.NewMessage(pattern=r'\.photo', from_users=user_id))
    async def photo(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на фото")
            return
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.respond("Это не фото")
            return
        try:
            photo = await reply.download_media()
            await client(UploadProfilePhotoRequest(await client.upload_file(photo)))
            await event.respond("Аватарка обновлена")
            os.remove(photo)
        except:
            await event.respond("Ошибка")

    @client.on(events.NewMessage(pattern=r'\.status', from_users=user_id))
    async def status(event):
        await event.delete()
        try:
            me = await client.get_me()
            dialogs = await client.get_dialogs()
            await event.respond(f"ID: {me.id}\nТелефон: {me.phone}\nЧатов: {len(dialogs)}")
        except:
            await event.respond(BETA_MSG)

    # 🖼 СТИКЕР
    @client.on(events.NewMessage(pattern=r'\.sticker', from_users=user_id))
    async def sticker(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на фото")
            return
        reply = await event.get_reply_message()
        if not reply.photo:
            await event.respond("Это не фото")
            return
        try:
            photo = await reply.download_media()
            img = Image.open(photo).resize((512, 512))
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                img.save(f.name, 'PNG')
                await client.send_file(event.chat_id, f.name)
                os.unlink(f.name)
            os.remove(photo)
        except:
            await event.respond(BETA_MSG)

    # 📊 ИНФО
    @client.on(events.NewMessage(pattern=r'\.wiki (.+)', from_users=user_id))
    async def wiki(event):
        await event.delete()
        try:
            query = event.pattern_match.group(1)
            r = requests.get(f'https://ru.wikipedia.org/api/rest_v1/page/summary/{query}')
            data = r.json()
            await event.respond(data['extract'][:500])
        except:
            await event.respond("Не найдено")

    @client.on(events.NewMessage(pattern=r'\.short (.+)', from_users=user_id))
    async def short(event):
        await event.delete()
        try:
            url = event.pattern_match.group(1)
            r = requests.get(f'https://is.gd/create.php?format=json&url={url}')
            data = r.json()
            await event.respond(data.get('shorturl', 'Ошибка'))
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.remind (\d+)([mhd]) (.+)', from_users=user_id))
    async def remind(event):
        await event.delete()
        amount = int(event.pattern_match.group(1))
        unit = event.pattern_match.group(2)
        text = event.pattern_match.group(3)
        seconds = amount * {'m': 60, 'h': 3600, 'd': 86400}[unit]
        await event.respond(f"Напомню через {amount}{unit}")
        await asyncio.sleep(seconds)
        await client.send_message(event.chat_id, text)

    @client.on(events.NewMessage(pattern=r'\.horo (.+)', from_users=user_id))
    async def horo(event):
        await event.delete()
        preds = ["Отличный день!", "Будьте осторожны с финансами.", "Ждите приятных сюрпризов."]
        await event.respond(random.choice(preds))

    # 🎲 ИГРЫ
    @client.on(events.NewMessage(pattern=r'\.duel (@\w+)', from_users=user_id))
    async def duel(event):
        await event.delete()
        winner = random.choice([event.sender_id, 'opponent'])
        if winner == event.sender_id:
            await event.respond(f"Победа над {event.pattern_match.group(1)}!")
        else:
            await event.respond(f"{event.pattern_match.group(1)} победил!")

    @client.on(events.NewMessage(pattern=r'\.roll(?: (\d+))?', from_users=user_id))
    async def roll(event):
        await event.delete()
        max_n = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else 100
        await event.respond(str(random.randint(1, max_n)))

    @client.on(events.NewMessage(pattern=r'\.slot', from_users=user_id))
    async def slot(event):
        await event.delete()
        symbols = ['🍒', '🍋', '🍊', '💎', '7️⃣']
        result = [random.choice(symbols) for _ in range(3)]
        win = len(set(result)) == 1
        await event.respond(f"{' '.join(result)} - {'Победа!' if win else 'Мимо'}")

    @client.on(events.NewMessage(pattern=r'\.guess (\d+)', from_users=user_id))
    async def guess(event):
        await event.delete()
        num = random.randint(1, 100)
        guess = int(event.pattern_match.group(1))
        if guess == num:
            await event.respond(f"Угадал! {num}")
        elif guess < num:
            await event.respond(f"Больше! Было {num}")
        else:
            await event.respond(f"Меньше! Было {num}")

    @client.on(events.NewMessage(pattern=r'\.rps (камень|ножницы|бумага)', from_users=user_id))
    async def rps(event):
        await event.delete()
        user = event.pattern_match.group(1)
        bot_choice = random.choice(['камень', 'ножницы', 'бумага'])
        if user == bot_choice:
            result = "Ничья"
        elif (user == 'камень' and bot_choice == 'ножницы') or (user == 'ножницы' and bot_choice == 'бумага') or (user == 'бумага' and bot_choice == 'камень'):
            result = "Победа"
        else:
            result = "Поражение"
        await event.respond(f"{result} (бот: {bot_choice})")

    @client.on(events.NewMessage(pattern=r'\.coin', from_users=user_id))
    async def coin(event):
        await event.delete()
        await event.respond(random.choice(['Орёл', 'Решка']))

    @client.on(events.NewMessage(pattern=r'\.wheel (.+)', from_users=user_id))
    async def wheel(event):
        await event.delete()
        options = [x.strip() for x in event.pattern_match.group(1).split(',')]
        await event.respond(random.choice(options))

    @client.on(events.NewMessage(pattern=r'\.8ball (.+)', from_users=user_id))
    async def ball8(event):
        await event.delete()
        await event.respond(random.choice(["Да", "Нет", "Возможно", "Определённо да", "Не сейчас"]))

    @client.on(events.NewMessage(pattern=r'\.luck', from_users=user_id))
    async def luck(event):
        await event.delete()
        await event.respond(f"{random.randint(1, 100)}%")

    @client.on(events.NewMessage(pattern=r'\.prediction', from_users=user_id))
    async def prediction(event):
        await event.delete()
        preds = ["Хороший день!", "Жди новостей", "Удача рядом", "Неожиданный сюрприз"]
        await event.respond(random.choice(preds))

    # 👮 МОДЕРАЦИЯ
    @client.on(events.NewMessage(pattern=r'\.mute (\d+)', from_users=user_id))
    async def mute(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на сообщение")
            return
        try:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            minutes = int(event.pattern_match.group(1))
            await client.edit_permissions(event.chat_id, user, send_messages=False, until_date=timedelta(minutes=minutes))
            await event.respond(f"Замучен на {minutes} мин")
        except:
            await event.respond("Нет прав")

    @client.on(events.NewMessage(pattern=r'\.unmute', from_users=user_id))
    async def unmute(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на сообщение")
            return
        try:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            await client.edit_permissions(event.chat_id, user, send_messages=True)
            await event.respond("Размучен")
        except:
            await event.respond("Нет прав")

    @client.on(events.NewMessage(pattern=r'\.kick', from_users=user_id))
    async def kick(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на сообщение")
            return
        try:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            await client.kick_participant(event.chat_id, user)
            await event.respond("Кикнут")
        except:
            await event.respond("Нет прав")

    @client.on(events.NewMessage(pattern=r'\.ban', from_users=user_id))
    async def ban(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на сообщение")
            return
        try:
            reply = await event.get_reply_message()
            user = await client.get_entity(reply.sender_id)
            await client.edit_permissions(event.chat_id, user, view_messages=False)
            await event.respond("Забанен")
        except:
            await event.respond("Нет прав")

    @client.on(events.NewMessage(pattern=r'\.warn', from_users=user_id))
    async def warn(event):
        await event.delete()
        if not event.is_reply:
            await event.respond("Ответь на сообщение")
            return
        reply = await event.get_reply_message()
        user = await client.get_entity(reply.sender_id)
        await event.respond(f"Предупреждение: {user.first_name}")

    # 🔍 OSINT
    @client.on(events.NewMessage(pattern=r'\.whois (.+)', from_users=user_id))
    async def whois(event):
        await event.delete()
        try:
            domain = event.pattern_match.group(1)
            r = requests.get(f'https://api.domainsdb.info/v1/domains/search?domain={domain}')
            data = r.json()
            if data['domains']:
                d = data['domains'][0]
                await event.respond(f"Создан: {d.get('create_date', 'N/A')}\nИстекает: {d.get('expiry_date', 'N/A')}")
            else:
                await event.respond("Не найдено")
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.dns (.+)', from_users=user_id))
    async def dns(event):
        await event.delete()
        try:
            domain = event.pattern_match.group(1)
            r = requests.get(f'https://dns.google/resolve?name={domain}&type=A')
            data = r.json()
            if 'Answer' in data:
                await event.respond("\n".join([a['data'] for a in data['Answer']]))
            else:
                await event.respond("Нет записей")
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.sub (.+)', from_users=user_id))
    async def sub(event):
        await event.delete()
        try:
            domain = event.pattern_match.group(1)
            r = requests.get(f'https://crt.sh/?q=%25.{domain}&output=json')
            data = r.json()
            subs = list(set([x['name_value'] for x in data[:50]]))
            await event.respond("\n".join(subs[:20]))
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.meta (.+)', from_users=user_id))
    async def meta(event):
        await event.delete()
        try:
            url = event.pattern_match.group(1)
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            title = re.findall(r'<title>(.*?)</title>', r.text, re.I)
            await event.respond(title[0] if title else "Нет заголовка")
        except:
            await event.respond(BETA_MSG)

    @client.on(events.NewMessage(pattern=r'\.social (.+)', from_users=user_id))
    async def social(event):
        await event.delete()
        username = event.pattern_match.group(1)
        platforms = {'GitHub': f'https://github.com/{username}', 'Twitter': f'https://twitter.com/{username}', 'Instagram': f'https://instagram.com/{username}'}
        await event.respond("\n".join([f"{p}: {u}" for p, u in platforms.items()]))

    # 📋 HELP
    @client.on(events.NewMessage(pattern=r'\.help', from_users=user_id))
    async def help_cmd(event):
        await event.delete()
        help_text = """🌙 **Lunar Phantom v0.0.1 Beta**

**📨 Рассылка:**
.broadcast текст — всем контактам
.bc текст — по группам
.bclist — список групп
.delay сек — задержка
.stopbc — остановить

**👥 Контакты:**
.ghosts — кто удалил
.mutual — взаимные
.nocontact — не в контактах
.search имя — поиск
.export — экспорт

**🎵 Музыка:**
.song запрос — поиск трека
.dl 1 — скачать MP3

**📸 Фото (reply):**
.ocr — текст с фото
.enhance — улучшить
.bw — ч/б
.blur — размыть
.compress — сжать

**🛠 Инструменты:**
.calc 2+2*3 — калькулятор
.usd 100 / .eur 50 / .rub 5000 / .cny 1000
.tr ru hello — перевод
.weather Москва — погода
.qr текст — QR-код
.morse привет / .unmorse .... . .-..
.pass 20 — пароль
.ip 8.8.8.8 — инфо IP
.time Москва — время
.dict hello — словарь

**💎 Крипта:**
.btc .eth .bnb .sol .doge
.top10 — топ-10

**🧹 Очистка:**
.clean — удалить 100 своих
.clean 50 — удалить N своих

**🎮 Развлечения:**
.dice .yesno .choose а, б .riddle

**🎲 Игры:**
.duel @user .roll 100 .slot
.guess 50 .rps камень
.coin .wheel а, б .8ball вопрос
.luck .prediction

**🔐 Кодирование:**
.b64enc / .b64dec .md5 .sha256
.hashid .rot13 .hex .urlenc / .urldec

**👤 Аккаунт:**
.bio .name .lastname .photo .status

**🖼 Медиа:**
.sticker — фото в стикер (reply)

**📊 Инфо:**
.wiki запрос — Википедия
.short url — сократить
.remind 10m текст — напомнить
.horo знак — гороскоп

**👮 Модерация (reply):**
.mute 10 .unmute .kick .ban .warn

**🔍 OSINT:**
.whois домен — WHOIS
.dns домен — DNS
.sub домен — поддомены
.meta url — заголовок сайта
.social ник — соцсети"""
        await event.respond(help_text)

    print(f"✅ Юзербот запущен: {phone}")
    await client.run_until_disconnected()

# ============ БОТ ============
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("🌙 **Lunar Phantom v0.0.1 Beta**", reply_markup=get_main_keyboard())

@dp.message_handler(lambda m: m.text == "❓ Помощь")
async def help_btn(message: types.Message):
    await message.reply("""📚 **Как запустить:**

1. Нажми «📱 Поделиться номером» или отправь номер (+79001234567)
2. Введи код из Telegram кнопками (5 цифр)
3. Если есть 2FA — введи пароль
4. Готово! Пиши .help в любом чате

Все команды начинаются с точки.
Примеры: .weather Москва, .btc, .dice""", reply_markup=get_main_keyboard())

@dp.message_handler(lambda m: m.text == "👤 Авторы")
async def authors_btn(message: types.Message):
    await message.reply("👤 Разработчик: Phantom\n📱 Telegram: @ECKAH0P\n🌙 Lunar Phantom v0.0.1 Beta", reply_markup=get_main_keyboard())

@dp.message_handler(content_types=['contact'])
async def process_contact(message: types.Message, state: FSMContext = None):
    await process_phone_number(message, message.contact.phone_number)

@dp.message_handler(lambda m: m.text and m.text.startswith('+'))
async def process_phone_text(message: types.Message):
    await process_phone_number(message, message.text.strip())

async def process_phone_number(message, phone):
    user_id = message.from_user.id
    try:
        temp_client = TelegramClient(f'session_{user_id}', API_ID, API_HASH)
        await temp_client.connect()
        sent_code = await temp_client.send_code_request(phone)
        auth_data[user_id] = {'client': temp_client, 'phone': phone, 'code_hash': sent_code.phone_code_hash, 'entered_code': ''}
        await message.reply("📱 Введи код из Telegram:\nКод: ▎▎▎▎▎", reply_markup=get_code_keyboard())
        await AuthStates.entering_code.set()
    except FloodWaitError as e:
        await message.reply(f"⚠️ Слишком много попыток. Подожди {e.seconds} секунд.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.callback_query_handler(lambda c: c.data.startswith('code_'), state=AuthStates.entering_code)
async def process_code_digit(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    action = callback_query.data.split('_')[1]
    
    if action == 'ok':
        code = auth_data[user_id]['entered_code']
        if len(code) < 5:
            await callback_query.answer("❌ Нужно 5 цифр!", show_alert=True)
            return
        try:
            temp_client = auth_data[user_id]['client']
            phone = auth_data[user_id]['phone']
            await temp_client.sign_in(phone=phone, code=code)
            await callback_query.message.edit_text("✅ Успешно! Юзербот запущен.\nПиши .help в любом чате.")
            await state.finish()
            asyncio.create_task(create_userbot(phone, user_id, temp_client))
        except SessionPasswordNeededError:
            await callback_query.message.edit_text("🔐 Введи пароль 2FA:")
            await AuthStates.waiting_password.set()
        except FloodWaitError as e:
            await callback_query.message.edit_text(f"⚠️ Слишком много попыток. Подожди {e.seconds} секунд.")
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Ошибка: {e}")
            await state.finish()
    elif action == 'del':
        auth_data[user_id]['entered_code'] = auth_data[user_id]['entered_code'][:-1]
    else:
        if len(auth_data[user_id]['entered_code']) >= 5:
            await callback_query.answer("❌ Уже 5 цифр! Нажми ✅", show_alert=True)
            return
        auth_data[user_id]['entered_code'] += action
    
    code = auth_data[user_id]['entered_code']
    await callback_query.message.edit_text(f"📱 Введи код:\nКод: {code}{'▎' * (5 - len(code))}", reply_markup=get_code_keyboard())
    await callback_query.answer()

@dp.message_handler(state=AuthStates.waiting_password)
async def process_password(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        temp_client = auth_data[user_id]['client']
        phone = auth_data[user_id]['phone']
        await temp_client.sign_in(password=message.text.strip())
        await message.reply("✅ Успешно! Юзербот запущен.\nПиши .help в любом чате.")
        await state.finish()
        asyncio.create_task(create_userbot(phone, user_id, temp_client))
    except FloodWaitError as e:
        await message.reply(f"⚠️ Слишком много попыток. Подожди {e.seconds} секунд.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")
        await state.finish()

@dp.message_handler()
async def other_messages(message: types.Message):
    await message.reply("Используй /start для начала работы", reply_markup=get_main_keyboard())

print("🌙 Lunar Phantom v0.0.1 Beta запущен...")
executor.start_polling(dp, skip_updates=True)
