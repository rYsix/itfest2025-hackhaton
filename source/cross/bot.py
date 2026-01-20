import threading
import logging
import time
import re

import telebot
from telebot import types

from openai import OpenAI
from django.conf import settings

from apps.support.models import SupportTicket, Client, Engineer
from cross.openai_use_case import OpenAIUseCase
from cross.utils import calculate_final_priority


# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)


# ============================================================
# SETTINGS
# ============================================================
BOT_TOKEN = settings.BOT_TOKEN
OPENAI_API_KEY = settings.OPENAI_KEY
OPENAI_MODEL = "gpt-3.5-turbo"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)


# Thread control
_bot_running = False
_bot_thread = None


# ============================================================
# SYSTEM PROMPTS (ПОЛНЫЕ ОПИСАНИЯ АССИСТЕНТА)
# ============================================================
SYSTEM_PROMPTS = {
    "ru": {
        "role": "system",
        "content": (
            "Ты — ОФИЦИАЛЬНЫЙ цифровой помощник АО «Казахтелеком», национального оператора связи Казахстана. "
            "Ты работаешь как первая линия ТЕХНИЧЕСКОЙ ПОДДЕРЖКИ. "
            "Твоя задача — помогать абонентам по услугам связи, интернета, телевидения и телефонии Казахтелекома.\n\n"
            "СТИЛЬ ОБЩЕНИЯ:\n"
            "- Пиши коротко, чётко и по делу.\n"
            "- Будь вежливым, спокойным и нейтральным.\n"
            "- Не используй сленг, шуточки и лишние эмоции.\n\n"
            "ПРЕДМЕТНАЯ ОБЛАСТЬ:\n"
            "- Отвечай ТОЛЬКО по услугам Казахтелекома.\n\n"
            "ВАЖНО: ты УЖЕ являешься ТЕХПОДДЕРЖКОЙ.\n"
            "- НЕ отправляй пользователя звонить куда-либо.\n\n"
            "ФОРМАТ:\n"
            "- Кратко и по делу."
        )
    },
    "kz": {
        "role": "system",
        "content": (
            "Сен — «Қазахтелеком» компаниясының ресми цифрлық көмекшісісің.\n"
            "Мақсатың — тек байланыс қызметтері бойынша көмектесу.\n"
            "Қысқа және нақты жауап бер."
        )
    }
}


# ============================================================
# UTILS
# ============================================================
def clean_markdown(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'####\s*(.+)', r'*\1*', text)
    text = re.sub(r'\[\[[^\]]+]]\([^)]+\)', '', text)
    return text.strip()


FLAG_KZ = "🇰🇿"
FLAG_RU = "🇷🇺"

user_language = {}       # user_id → "ru"/"kz"
user_state = {}          # user_id → {"step": "...", ...}


def make_lang_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton(FLAG_KZ), types.KeyboardButton(FLAG_RU))
    kb.row(types.KeyboardButton("/help"))
    return kb


def make_help_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("/help"), types.KeyboardButton("/new"))
    return kb


lang_keyboard = make_lang_keyboard()
help_keyboard = make_help_keyboard()


# ============================================================
# SEARCH SIMILAR SOLUTIONS
# ============================================================
def find_similar_solutions(user_text: str) -> list:
    if not user_text:
        return []

    text = user_text.lower()
    qs = SupportTicket.objects.filter(final_resolution__isnull=False).exclude(final_resolution="")

    matches = []
    for t in qs[:200]:
        desc = (t.description or "").lower()
        if len(text) > 5 and text in desc:
            matches.append({"id": t.id, "solution": t.final_resolution})

    return sorted(matches, key=lambda x: x["id"], reverse=True)[:3]


def format_similar_solutions(lang: str, solutions: list) -> str:
    if not solutions:
        return ""

    header = "🔎 *Похожие решения техподдержки:*\n" if lang == "ru" else "🔎 *Ұқсас шешімдер:*\n"
    lines = [f"• Тикет #{s['id']}: {s['solution']}" for s in solutions]
    return header + "\n".join(lines) + "\n\n"


# ============================================================
# COMMAND HANDLERS
# ============================================================
@bot.message_handler(commands=['start'])
def cmd_start(message: types.Message):
    bot.send_message(message.chat.id, "Выберите язык: 🇰🇿 или 🇷🇺", reply_markup=lang_keyboard)


@bot.message_handler(commands=['help'])
def cmd_help(message: types.Message):
    lang = user_language.get(message.from_user.id, "ru")
    text = {
        "ru": "Команды:\n/new — создать заявку\n/help — помощь\n/lang — язык",
        "kz": "Командалар:\n/new — өтініш\n/help — көмек\n/lang — тіл",
    }
    bot.send_message(message.chat.id, text[lang], reply_markup=help_keyboard)


@bot.message_handler(commands=['lang'])
def cmd_lang(message: types.Message):
    bot.send_message(message.chat.id, "Выберите язык: 🇰🇿 или 🇷🇺", reply_markup=lang_keyboard)


@bot.message_handler(commands=['new'])
def cmd_new(message: types.Message):
    user_id = message.from_user.id
    lang = user_language.get(user_id, "ru")
    user_state[user_id] = {"step": "full_name"}
    prompts = {"ru": "Введите ФИО:", "kz": "Аты-жөніңіз:"}
    bot.send_message(message.chat.id, prompts[lang], reply_markup=help_keyboard)


# ============================================================
# MAIN MESSAGE PROCESSOR
# ============================================================
@bot.message_handler(content_types=['text'])
def handle_text(message: types.Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

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

    if user_id in user_state:
        process_ticket_dialog(message, user_id, text, lang)
        return

    similar = find_similar_solutions(text)
    similar_block = format_similar_solutions(lang, similar)

    try:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[SYSTEM_PROMPTS[lang], {"role": "user", "content": text}],
            temperature=0.15,
        )
        answer = clean_markdown(resp.choices[0].message.content or "")
        bot.send_message(message.chat.id, similar_block + answer, reply_markup=help_keyboard)
    except Exception:
        bot.send_message(message.chat.id, "Ошибка сервера.", reply_markup=help_keyboard)


# ============================================================
# TICKET CREATION DIALOG
# ============================================================
def process_ticket_dialog(message: types.Message, user_id: int, text: str, lang: str):
    state = user_state[user_id]
    chat_id = message.chat.id

    if state["step"] == "full_name":
        state["full_name"] = text
        state["step"] = "account"
        bot.send_message(chat_id, "Введите номер лицевого счёта:" if lang == "ru" else "Жеке шот нөмірі:")
        return

    if state["step"] == "account":
        state["account_number"] = text
        state["step"] = "description"
        bot.send_message(chat_id, "Опишите проблему:" if lang == "ru" else "Мәселені сипаттаңыз:")
        return

    if state["step"] == "description":
        if not OpenAIUseCase.classify_telecom_issue(text):
            bot.send_message(chat_id, "Проблема не относится к услугам Казахтелекома.")
            user_state.pop(user_id, None)
            return

        client = Client.objects.filter(account_number=state["account_number"]).first()
        if not client:
            bot.send_message(chat_id, "Клиент не найден.")
            user_state.pop(user_id, None)
            return

        ai = OpenAIUseCase.generate_full_ticket_ai(text, client.age)
        if ai is None:
            bot.send_message(chat_id, "AI временно недоступен.")
            user_state.pop(user_id, None)
            return

        final_priority = calculate_final_priority(int(ai.get("initial_priority", 50)), client)

        ticket = SupportTicket.objects.create(
            client=client,
            description=text,
            priority_score=final_priority,
            engineer_visit_probability=ai.get("engineer_probability", 0),
            why_engineer_needed=ai.get("engineer_probability_explanation", ""),
            proposed_solution_engineer=ai.get("engineer_advice", ""),
            proposed_solution_client=ai.get("client_advice", ""),
            status="new",
        )

        # ----------------------------------------------------
        # AI → ПОДБОР ИНЖЕНЕРА ДЛЯ TG-СОЗДАНИЯ
        # ----------------------------------------------------
        engineer_pick = OpenAIUseCase.pick_engineer_for_ticket(ticket)
        if engineer_pick:
            engineer = Engineer.objects.filter(
                id=engineer_pick.get("engineer_id"),
                is_active=True
            ).first()
            if engineer:
                ticket.engineer = engineer
                ticket.save(update_fields=["engineer"])

                logger.info(
                    "AI engineer assigned (TG)",
                    extra={
                        "ticket_id": ticket.id,
                        "engineer_id": engineer.id,
                        "confidence": engineer_pick.get("confidence"),
                    }
                )

        msg = (
            f"✨ Заявка создана!\nНомер: #{ticket.id}\n\n{ai.get('client_advice')}"
            if lang == "ru"
            else f"✨ Өтініш жасалды!\nНөмірі: #{ticket.id}\n\n{ai.get('client_advice')}"
        )

        bot.send_message(chat_id, msg, reply_markup=help_keyboard)
        user_state.pop(user_id, None)


# ============================================================
# BOT THREAD CONTROL
# ============================================================
def _polling_loop():
    global _bot_running
    logger.info("Bot thread started")

    while _bot_running:
        try:
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
        except Exception:
            logger.exception("Bot crashed — restarting")
            time.sleep(3)

    logger.info("Bot thread exited")


def start_bot():
    global _bot_running, _bot_thread
    if _bot_running:
        return False

    _bot_running = True
    _bot_thread = threading.Thread(
        target=_polling_loop,
        name="telegram_bot_thread",
        daemon=True,
    )
    _bot_thread.start()

    logger.info("Bot STARTED")
    return True


def stop_bot():
    global _bot_running
    if not _bot_running:
        return False

    _bot_running = False
    logger.info("Bot STOP requested")
    return True
