import threading
import logging
import time
import re

import telebot
from telebot import types

from openai import OpenAI
from django.conf import settings

from apps.support.models import SupportTicket, Client
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
            "- Не используй сленг, шуточки и лишние эмоции.\n"
            "- Не драматизируй и не пугай пользователя.\n\n"

            "ПРЕДМЕТНАЯ ОБЛАСТЬ (ЖЁСТКОЕ ОГРАНИЧЕНИЕ):\n"
            "- Отвечай ТОЛЬКО по услугам Казахтелекома: интернет, ТВ, телефония, роутеры, модемы, оптика, тарифы, оплата.\n"
            "- Если вопрос НЕ относится к услугам Казахтелекома, прямо и вежливо скажи, что ты можешь помогать только по вопросам связи "
            "и услуг компании, и не отвечай по другим темам.\n\n"

            "ВАЖНО: ты УЖЕ являешься ТЕХПОДДЕРЖКОЙ.\n"
            "- НЕ нужно советовать «позвонить в поддержку», «обратиться в техподдержку», «позвонить оператору» и т.п.\n"
            "- Отвечай так, как если бы ты был оператором технической поддержки первого уровня.\n"
            "- Если нужно, можешь написать, что при сохранении проблемы инженер или оператор свяжется с клиентом позже, но не отправляй его "
            "«звонить в поддержку».\n\n"

            "ПОВЕДЕНИЕ ПРИ ПРОБЛЕМАХ:\n"
            "- Помогай последовательно: сначала понять проблему, затем предложить безопасные шаги.\n"
            "- Разрешено предлагать:\n"
            "  * перезагрузку роутера/модема через выключение и включение питания;\n"
            "  * проверку кабелей, питания, индикаторов;\n"
            "  * проверку логина/пароля PPPoE, если это явно уместно;\n"
            "  * проверку оплаты и наличия задолженности, если по описанию похоже на блокировку.\n"
            "- НЕЛЬЗЯ предлагать опасные или слишком технические действия (скрытые инженерные меню, сложные настройки, прошивку и т.д.).\n\n"

            "ЕСЛИ ВОПРОС НЕ ИЗ ТЕЛЕКОМ-СФЕРЫ:\n"
            "- Вежливо объясни, что ты ассистент Казахтелекома и можешь помогать только по вопросам связи и услуг компании.\n"
            "- Не пытайся отвечать на медицинские, финансовые, политические, юридические, бытовые и прочие посторонние вопросы.\n\n"

            "ФОРМАТ ОТВЕТА:\n"
            "- Краткий, структурированный и понятный текст.\n"
            "- Если нужно несколько шагов, оформи списком.\n"
            "- Избегай длинных «простыней».\n"
        )
    },
    "kz": {
        "role": "system",
        "content": (
            "Сен — АО «Қазахтелеком» ұлттық байланыс операторының РЕСМИ цифрлық көмекшісісің. "
            "Сен техникалық қолдаудың бірінші деңгейі ретінде жұмыс істейсің. "
            "Міндетің — интернет, теледидар, телефония және басқа да байланыс қызметтері бойынша абоненттерге көмектесу.\n\n"

            "ҚАРЫМ-ҚАТЫНАС СТИЛІ:\n"
            "- Қысқа, түсінікті және нақты жауап бер.\n"
            "- Сыпайы, сабырлы және бейтарап бол.\n"
            "- Сленг, әзіл-қалжың және қажетсіз эмоция қолданба.\n\n"

            "ПӘНДІК АЯ (ҚАТАҢ ШЕКТЕУ):\n"
            "- ТЕК «Қазахтелеком» қызметтері туралы жауап бер: интернет, ТВ, телефония, маршрутизатор, модем, оптика, тарифтер, төлем.\n"
            "- Егер сұрақ компания қызметіне қатысы жоқ болса, сыпайы түрде тек байланыс қызметтері бойынша көмек көрсете алатыныңды айт.\n\n"

            "МАҢЫЗДЫ: сен ҚАЗІРдің өзінде техникалық қолдау операторысың.\n"
            "- «Қолдау қызметіне қоңырау шалыңыз», «оператормен байланысыңыз» деген кеңестерді берме.\n"
            "- Өз жауаптарыңды бірінші деңгейдегі техникалық қолдау маманы сияқты құр.\n\n"

            "МӘСЕЛЕ КЕЗІНДЕ:\n"
            "- Алдымен мәселені түсінуге тырыс, кейін қауіпсіз қадамдарды ұсын.\n"
            "- Рұқсат етілген кеңестер: құрылғыны өшіру/қосу, кабельді тексеру, индикаторларды қарау, қажет болса төлемді/қарызды тексеру.\n"
            "- Қауіпті немесе тым күрделі әрекеттерді (жасырын инженерлік мәзір, күрделі баптаулар, микробағдарлама) ұсынба.\n\n"

            "ЕГЕР СҰРАҚ БАЙЛАНЫСҚА ҚАТЫСЫ ЖОҚ БОЛСА:\n"
            "- Сен тек «Қазахтелеком» байланыс қызметтері бойынша көмектесетін көмекші екеніңді түсіндір.\n"
            "- Медицина, саясат, қаржы, заң, тұрмыстық немесе өзге де тақырыптар бойынша жауап берме.\n\n"

            "ЖАУАП ФОРМАТЫ:\n"
            "- Қысқа, құрылымды, түсінікті мәтін.\n"
            "- Бірнеше қадам керек болса, тізім ретінде жаз.\n"
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
    """
    Ищет похожие тикеты, у которых есть final_resolution.
    Возвращает [{ "id": 123, "solution": "..." }, ...]
    """
    if not user_text:
        return []

    text = user_text.lower()

    qs = (
        SupportTicket.objects
        .filter(final_resolution__isnull=False)
        .exclude(final_resolution="")
    )

    matches = []
    for t in qs[:200]:
        desc = (t.description or "").lower()
        if len(text) > 5 and text in desc:
            matches.append({"id": t.id, "solution": t.final_resolution})

    return sorted(matches, key=lambda x: x["id"], reverse=True)[:3]


def format_similar_solutions(lang: str, solutions: list) -> str:
    if not solutions:
        return ""

    if lang == "ru":
        header = "🔎 *Похожие решения техподдержки:*\n"
    else:
        header = "🔎 *Ұқсас шешімдер (техқолдау):*\n"

    lines = []
    for s in solutions:
        lines.append(f"• Тикет #{s['id']}: {s['solution']}")

    return header + "\n".join(lines) + "\n\n"


# ============================================================
# COMMAND HANDLERS
# ============================================================
@bot.message_handler(commands=['start'])
def cmd_start(message: types.Message):
    bot.send_message(
        message.chat.id,
        "Здравствуйте! Выберите язык: 🇰🇿 или 🇷🇺",
        reply_markup=lang_keyboard,
    )


@bot.message_handler(commands=['help'])
def cmd_help(message: types.Message):
    user_id = message.from_user.id
    lang = user_language.get(user_id, "ru")

    text = {
        "ru": "Команды:\n/new — создать заявку\n/help — помощь\n/lang — сменить язык",
        "kz": "Командалар:\n/new — өтініш жасау\n/help — көмек\n/lang — тілді ауыстыру",
    }

    bot.send_message(message.chat.id, text[lang], reply_markup=help_keyboard)


@bot.message_handler(commands=['lang'])
def cmd_lang(message: types.Message):
    bot.send_message(
        message.chat.id,
        "Выберите язык: 🇰🇿 или 🇷🇺",
        reply_markup=lang_keyboard,
    )


# ============================================================
# START NEW TICKET CREATION
# ============================================================
@bot.message_handler(commands=['new'])
def cmd_new(message: types.Message):
    user_id = message.from_user.id
    lang = user_language.get(user_id, "ru")

    user_state[user_id] = {"step": "full_name"}

    prompt = {
        "ru": "Введите ваше ФИО:",
        "kz": "Аты-жөніңізді енгізіңіз:",
    }

    bot.send_message(message.chat.id, prompt[lang], reply_markup=help_keyboard)


# ============================================================
# MAIN MESSAGE PROCESSOR
# ============================================================
@bot.message_handler(content_types=['text'])
def handle_text(message: types.Message):
    user_id = message.from_user.id
    text = (message.text or "").strip()

    # --------------------------
    # Language selection
    # --------------------------
    if text == FLAG_KZ:
        user_language[user_id] = "kz"
        bot.send_message(message.chat.id, "Тіл сақталды.", reply_markup=help_keyboard)
        return

    if text == FLAG_RU:
        user_language[user_id] = "ru"
        bot.send_message(message.chat.id, "Язык сохранён.", reply_markup=help_keyboard)
        return

    if user_id not in user_language:
        bot.send_message(
            message.chat.id,
            "Выберите язык: 🇰🇿 или 🇷🇺",
            reply_markup=lang_keyboard,
        )
        return

    lang = user_language[user_id]

    # --------------------------
    # If user is in ticket-creation dialog
    # --------------------------
    if user_id in user_state:
        process_ticket_dialog(message, user_id, text, lang)
        return

    # --------------------------
    # Regular AI + similar suggestions
    # --------------------------
    similar = find_similar_solutions(text)
    similar_block = format_similar_solutions(lang, similar)

    try:
        resp = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                SYSTEM_PROMPTS[lang],
                {"role": "user", "content": text},
            ],
            max_tokens=600,
            temperature=0.15,
        )

        gpt_result = clean_markdown(resp.choices[0].message.content or "")
        final_message = similar_block + gpt_result

        bot.send_message(message.chat.id, final_message, reply_markup=help_keyboard)

    except Exception:
        fallback = {
            "ru": "Сервер недоступен. Попробуйте позже.",
            "kz": "Сервер қолжетімсіз. Кейінірек қайталап көріңіз.",
        }
        bot.send_message(message.chat.id, fallback[lang], reply_markup=help_keyboard)


# ============================================================
# TICKET CREATION DIALOG LOGIC
# ============================================================
def process_ticket_dialog(message: types.Message, user_id: int, text: str, lang: str):
    state = user_state[user_id]
    step = state["step"]

    chat_id = message.chat.id

    # ------------------------------
    # 1. FULL NAME
    # ------------------------------
    if step == "full_name":
        state["full_name"] = text
        state["step"] = "account"

        prompts = {
            "ru": "Введите номер лицевого счёта:",
            "kz": "Жеке шот нөмірін енгізіңіз:",
        }

        bot.send_message(chat_id, prompts[lang])
        return

    # ------------------------------
    # 2. ACCOUNT NUMBER
    # ------------------------------
    if step == "account":
        state["account_number"] = text
        state["step"] = "description"

        prompts = {
            "ru": "Опишите проблему:",
            "kz": "Мәселені сипаттаңыз:",
        }

        bot.send_message(chat_id, prompts[lang])
        return

    # ------------------------------
    # 3. DESCRIPTION → PROCESS
    # ------------------------------
    if step == "description":
        state["description"] = text

        # 1) Проверка «телеком / не телеком»
        if not OpenAIUseCase.classify_telecom_issue(text):
            msg = {
                "ru": "Описание не относится к услугам Казахтелекома. Заявка не создана.",
                "kz": "Сипаттама «Қазахтелеком» қызметтеріне қатысы жоқ. Өтініш жасалмады.",
            }
            bot.send_message(chat_id, msg[lang], reply_markup=help_keyboard)
            user_state.pop(user_id, None)
            return

        # 2) Поиск клиента по лицевому счёту
        client = Client.objects.filter(account_number=state["account_number"]).first()
        if client is None:
            msg = {
                "ru": "Клиент с таким лицевым счётом не найден. Проверьте данные.",
                "kz": "Мұндай жеке шот нөмірі бойынша клиент табылмады. Мәліметтерді тексеріңіз.",
            }
            bot.send_message(chat_id, msg[lang], reply_markup=help_keyboard)
            user_state.pop(user_id, None)
            return

        # 3) AI: единый запрос
        ai = OpenAIUseCase.generate_full_ticket_ai(
            state["description"],
            client.age,
        )

        if ai is None:
            msg = {
                "ru": "AI-сервис временно недоступен. Попробуйте позже.",
                "kz": "AI-сервис уақытша қолжетімсіз. Кейінірек қайталап көріңіз.",
            }
            bot.send_message(chat_id, msg[lang], reply_markup=help_keyboard)
            user_state.pop(user_id, None)
            return

        client_advice = ai.get("client_advice", "")
        engineer_advice = ai.get("engineer_advice", "")
        engineer_prob = ai.get("engineer_probability", 0)
        engineer_prob_expl = ai.get("engineer_probability_explanation", "")
        initial_priority = ai.get("initial_priority", 50)

        final_priority = calculate_final_priority(int(initial_priority), client)

        # 4) СОЗДАНИЕ ТИКЕТА
        ticket = SupportTicket.objects.create(
            client=client,
            description=state["description"],
            priority_score=final_priority,
            engineer_visit_probability=engineer_prob,
            why_engineer_needed=engineer_prob_expl,
            proposed_solution_engineer=engineer_advice,
            proposed_solution_client=client_advice,
            status="new",
        )

        # 5) ОТВЕТ ПОЛЬЗОВАТЕЛЮ
        if lang == "ru":
            text_answer = (
                f"✨ *Заявка создана!*\n\n"
                f"Номер: #{ticket.id}\n"
                f"*Рекомендация для клиента:*\n{client_advice}"
            )
        else:
            text_answer = (
                f"✨ *Өтініш сәтті жасалды!*\n\n"
                f"Нөмірі: #{ticket.id}\n"
                f"*Клиентке ұсыныс:*\n{client_advice}"
            )

        bot.send_message(chat_id, text_answer, parse_mode="Markdown", reply_markup=help_keyboard)

        # Очистка state
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
            logger.exception("Bot crashed — restarting in 3 seconds")
            time.sleep(3)

    logger.info("Bot thread exited")


def start_bot():
    """
    Запуск бота извне (например, из Django view или management-команды).
    """
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
    """
    Остановка бота.
    """
    global _bot_running

    if not _bot_running:
        return False

    _bot_running = False
    logger.info("Bot STOP requested")
    return True
