import threading
import logging
import time
import re

import telebot
from telebot import types

from openai import OpenAI
from django.conf import settings

from apps.support.models import SupportTicket


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)

# ============================================================
# KEY SETTINGS
# ============================================================

BOT_TOKEN = settings.BOT_TOKEN
OPENAI_API_KEY = settings.OPENAI_KEY
OPENAI_MODEL = "gpt-3.5-turbo"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)


# Флаг и поток бота
_bot_running = False
_bot_thread = None


# ============================================================
# SYSTEM PROMPTS
# ============================================================

SYSTEM_PROMPTS = {
    "ru": {
        "role": "system",
        "content": (
            "Ты — официальный цифровой помощник АО «Казахтелеком»..."
            "Если вопрос явно не относится к Казахтелеком — вежливо сообщи."
        )
    },
    "kz": {
        "role": "system",
        "content": (
            "Сен — АО «Қазахтелеком» компаниясының ресми цифрлық көмекшісісің..."
            "Пайдаланушы сұрағы компанияға қатысы жоқ болса — сыпайы түрде хабарла."
        )
    }
}


# ============================================================
# UTILITIES
# ============================================================

def clean_markdown(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'####\s*(.+)', r'*\1*', text)
    text = re.sub(r'\[\[[^\]]+]]\([^)]+\)', '', text)
    return text.strip()


FLAG_KZ = "🇰🇿"
FLAG_RU = "🇷🇺"

user_language = {}


def make_lang_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton(FLAG_KZ), types.KeyboardButton(FLAG_RU))
    kb.row(types.KeyboardButton("/help"))
    return kb


def make_help_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("/help"))
    return kb


lang_keyboard = make_lang_keyboard()
help_keyboard = make_help_keyboard()


# ============================================================
# LOCAL DB SEARCH: SIMILAR PAST SOLUTIONS
# ============================================================

def find_similar_solutions(user_text: str) -> list:
    """
    Ищет похожие тикеты, у которых есть final_resolution.
    Возвращает список словарей:
        [{ "id": 123, "solution": "текст" }, ...]
    """
    if not user_text:
        return []

    text = user_text.lower()

    # простейший поиск по вхождению
    qs = (
        SupportTicket.objects
        .filter(final_resolution__isnull=False)
        .exclude(final_resolution="")
    )

    matches = []
    for t in qs[:200]:  # ограничение на выборку
        desc = (t.description or "").lower()
        if len(text) > 5 and text in desc:
            matches.append({"id": t.id, "solution": t.final_resolution})

    # сортируем по ID (новые выше)
    matches = sorted(matches, key=lambda x: x["id"], reverse=True)

    return matches[:3]  # максимум 3 решения


def format_similar_solutions(lang: str, solutions: list) -> str:
    if not solutions:
        return ""

    if lang == "ru":
        header = "🔎 *Похожие решения от техподдержки:*\n"
    else:
        header = "🔎 *Ұқсас шешімдер (ТҚ):*\n"

    body_lines = []
    for s in solutions:
        body_lines.append(f"• Тикет #{s['id']}: {s['solution']}")

    return header + "\n".join(body_lines) + "\n\n"


# ============================================================
# BOT COMMAND HANDLERS
# ============================================================

@bot.message_handler(commands=['start'])
def cmd_start(message: types.Message):
    bot.send_message(
        message.chat.id,
        "Здравствуйте! Выберите язык: 🇰🇿 или 🇷🇺",
        reply_markup=lang_keyboard
    )


@bot.message_handler(commands=['help'])
def cmd_help(message: types.Message):
    user_id = message.from_user.id
    lang = user_language.get(user_id, "ru")

    if lang == "ru":
        bot.send_message(message.chat.id, "Команды: /start /help /lang", reply_markup=help_keyboard)
    else:
        bot.send_message(message.chat.id, "Командалар: /start /help /lang", reply_markup=help_keyboard)


@bot.message_handler(commands=['lang'])
def cmd_lang(message: types.Message):
    bot.send_message(message.chat.id, "Выберите язык: 🇰🇿 или 🇷🇺", reply_markup=lang_keyboard)


# ============================================================
# MAIN TEXT HANDLER (AI)
# ============================================================

@bot.message_handler(content_types=['text'])
def handle_text(message: types.Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    # Языковые переключатели
    if text == FLAG_KZ:
        user_language[user_id] = "kz"
        bot.send_message(message.chat.id, "Тіл сақталды.", reply_markup=help_keyboard)
        return

    if text == FLAG_RU:
        user_language[user_id] = "ru"
        bot.send_message(message.chat.id, "Язык сохранён.", reply_markup=help_keyboard)
        return

    if user_id not in user_language:
        bot.send_message(message.chat.id, "Выберите язык: 🇰🇿 или 🇷🇺", reply_markup=lang_keyboard)
        return

    lang = user_language[user_id]

    # --------------------------------------------------------
    # 1. Поиск похожих решений из локальной базы
    # --------------------------------------------------------
    similar = find_similar_solutions(text)
    similar_block = format_similar_solutions(lang, similar)

    # --------------------------------------------------------
    # 2. GPT запрос
    # --------------------------------------------------------
    try:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                SYSTEM_PROMPTS[lang],
                {"role": "user", "content": text}
            ],
            max_tokens=600,
            temperature=0.15,
        )

        gpt_result = clean_markdown(resp.choices[0].message.content)

        final_message = similar_block + gpt_result

        bot.send_message(message.chat.id, final_message, reply_markup=help_keyboard)

    except Exception:
        fallback = {
            "ru": "Сервер недоступен. Попробуйте позже.",
            "kz": "Сервер қолжетімсіз. Кейінірек қайталап көріңіз."
        }
        bot.send_message(message.chat.id, fallback[lang], reply_markup=help_keyboard)


# ============================================================
# BOT THREAD CONTROL (FOR DJANGO)
# ============================================================

def _polling_loop():
    global _bot_running

    logger.info("Bot thread started")

    while _bot_running:
        try:
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
        except Exception:
            logger.exception("Bot crashed — restarting in 3 seconds")
            time.sleep(3)

    logger.info("Bot thread EXITED")


def start_bot():
    """
    Запуск бота извне (через view).
    """
    global _bot_running, _bot_thread

    if _bot_running:
        return False

    _bot_running = True

    _bot_thread = threading.Thread(
        target=_polling_loop,
        name="telegram_bot_thread",
        daemon=True
    )
    _bot_thread.start()

    logger.info("Bot STARTED")
    return True


def stop_bot():
    """
    Остановка бота.
    """
    global _bot_running

    if not _bot_running:
        return False

    _bot_running = False
    logger.info("Bot STOP requested")

    return True
