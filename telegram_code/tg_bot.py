import json
import logging
import os
import time
from datetime import datetime, timedelta
from enum import Enum, auto
from textwrap import dedent
from typing import Dict
from telegram.utils.request import Request

import environs
import phonenumbers
import requests
import telegram
from bs4 import BeautifulSoup
from more_itertools import chunked
from telegram import (Bot, Chat, InlineKeyboardButton, InlineKeyboardMarkup,
                      KeyboardButton, LabeledPrice, Message, ParseMode,
                      ReplyKeyboardMarkup, Update)
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, ConversationHandler, Filters,
                          MessageHandler, PreCheckoutQueryHandler, Updater)

from text_filters import (ValidLessonFilter, ValidPracticeFilter,
                          ValidTariffFilter, ValidTestsFilter,
                          ValidTopicFilter, ValidVideoFilter)
from utils import (call_api_get, call_api_post, clean_html,
                   delete_previous_messages, download_youtube_video,
                   validate_phone_number)

class States(Enum):
    MAIN_MENU = auto()
    TOPICS_MENU = auto()
    TOPIC = auto()
    ADMIN = auto()
    ACCEPT_PRIVACY = auto()
    START_REGISTRATION = auto()
    USER_FULLNAME = auto()
    USER_EMAIL = auto()
    USER_PHONE_NUMBER = auto()
    TEST_LEVEL = auto()
    TEST_START = auto()
    TEST_QUESTION = auto()
    TEST_RESULT = auto()
    TARIFF = auto()
    PAYMENT = auto()
    AVAILABLE_TOPIC = auto()
    AVAILABLE_LESSON = auto()
    AVAILABLE_ITEMS = auto()
    AVAILABLE_CONTENT = auto()
    AVAILABLE_QUESTION = auto()
    AVAILABLE_FINISH = auto()
    AVAILABLE_FINISH_VIDEO = auto()
    AVAILABLE_FINISH_TEST = auto()
    AVAILABLE_FINISH_PRACTICE = auto()
    ADMIN_ANSWER = auto()
    PRACTICE = auto()
    INVOICE = auto()


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_telegram_id(update: Update, context: CallbackContext) -> int:
    """Извлекает telegram_id из update или context."""
    if update.callback_query:
        return context.user_data.get("telegram_id", update.effective_user.id)
    return update.message.from_user.id


def get_user_role(telegram_id: int) -> str:
    """Получает роль пользователя через API."""
    try:
        response = call_api_get(f"bot/tg_user/{telegram_id}")
        response.raise_for_status()
        user_data = response.json()
        return user_data.get("role", "user")
    except Exception as e:
        logger.error(f"Ошибка получения роли пользователя {telegram_id}: {e}")
        return "user"


def handle_api_error(update: Update, context: CallbackContext, error: Exception, chat_id: int):
    """Обрабатывает ошибку API и возвращает состояние ADMIN."""
    delete_previous_messages(context, chat_id)
    menu_msg = "Ошибка при загрузке информации, перешлите это сообщение администратору"
    telegram_id = get_telegram_id(update, context)
    error_msg = dedent(f"""\
        <b>Ошибка при загрузке информации:</b>
        {str(error)}

        <b>telegram_id пользователя:</b>
        {telegram_id}
    """).replace("  ", "")
    context.user_data['tariff_show_error'] = error_msg
    is_callback = bool(update.callback_query)
    keyboard = [["📖 Главное меню", "🛠 Написать Админу"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    admin_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)

    if 'prev_message_ids' not in context.user_data:
        context.user_data['prev_message_ids'] = []
    context.user_data['prev_message_ids'].append(admin_message_id)


def send_message_bot(context: CallbackContext, update: Update, text: str, markup, is_callback: bool = False,
                     chat_id: int = None) -> int:
    """Отправляет сообщение в зависимости от типа update (callback или message) и возвращает message_id."""
    if chat_id is None:
        if is_callback and update and update.callback_query:
            chat_id = update.callback_query.message.chat.id
        elif update and update.effective_message:
            chat_id = update.effective_chat.id
        else:
            chat_id = context.user_data.get('chat_id')
            if not chat_id:
                raise ValueError("Не удалось определить chat_id")

    message = context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=markup,
        parse_mode=ParseMode.HTML
    )
    return message.message_id


def add_content_via_api(endpoint: str, payload: Dict, context: CallbackContext, update: Update = None) -> [Dict, str, Dict]:
    """
    Вызывает API для добавления контента и возвращает данные о новом контенте.

    Args:
        endpoint: URL API (например, '/bot/next_content/add/').
        payload: Данные для POST-запроса (например, {'user_id': 1, 'video_id': 2}).
        context: CallbackContext для доступа к боту.
        update: Update для отправки сообщений.

    Returns:
        Словарь с новым контентом или пустой словарь при ошибке.
    """
    try:
        response = call_api_post(endpoint, payload)
        response.raise_for_status()
        content_data = response.json()
        next_content = content_data.get("next_content", {})
        next_step = content_data.get("next_step", None)
        next_step_params = content_data.get("next_step_params", {})
        if not next_content:
            logger.warning(f"Нет next_content в ответе API: {content_data}")
        return next_content, next_step, next_step_params
    except Exception as e:
        logger.error(f"Ошибка API ({endpoint}): {str(e)}")
        send_message_bot(context, update, "Ошибка при обновлении контента.", None, False)
        return {}


def format_content_message(next_content: Dict) -> str:
    """
    Форматирует сообщение о новом доступном контенте.
    """
    topics_str = "\n".join(next_content.get('next_topics_name', ['Нет новых тем'])) or "Нет новых тем"
    lessons_str = "\n".join(next_content.get('next_lessons_name', ['Нет новых уроков'])) or "Нет новых уроков"
    videos_str = "\n".join(next_content.get('next_videos_name', ['Нет новых видео'])) or "Нет новых видео"
    tests_str = "\n".join(next_content.get('next_tests_name', ['Нет новых тестов'])) or "Нет новых тестов"
    practices_str = "\n".join(next_content.get('next_practices_name', ['Нет новых практик'])) or "Нет новых практик"

    return dedent(f"""\
        Вы правильно ответили, вам доступен следующий контент:
        <b>Темы:</b>
        {topics_str}
        <b>Уроки:</b>
        {lessons_str}
        <b>Видео:</b>
        {videos_str}
        <b>Тесты:</b>
        {tests_str}
        <b>Практики:</b>
        {practices_str}
    """).replace("  ", "")


def format_done_message(content_done: Dict) -> str:
    """
    Форматирует сообщение о пройденном контенте.
    """
    topics_str = "\n".join(
        content_done.get('names_done', {}).get('names_done_topics', ['Нет пройденных тем'])) or "Нет пройденных тем"
    lessons_str = "\n".join(content_done.get('names_done', {}).get('names_done_lessons', [
        'Нет пройденных уроков'])) or "Нет пройденных уроков"
    videos_str = "\n".join(
        content_done.get('names_done', {}).get('names_done_videos', ['Нет пройденных видео'])) or "Нет пройденных видео"
    tests_str = "\n".join(content_done.get('names_done', {}).get('names_done_tests',
                                                                 ['Нет пройденных тестов'])) or "Нет пройденных тестов"
    practices_str = "\n".join(content_done.get('names_done', {}).get('names_done_practices', [
        'Нет пройденных практик'])) or "Нет пройденных практик"

    topics_done = content_done['quantity_done']['quantity_done_topics']
    lessons_done = content_done['quantity_done']['quantity_done_lessons']
    videos_done = content_done['quantity_done']['quantity_done_videos']
    tests_done = content_done['quantity_done']['quantity_done_tests']
    practices_done = content_done['quantity_done']['quantity_done_practices']

    topics_all = content_done['quantity_all']['topics']
    lessons_all = content_done['quantity_all']['lessons']
    videos_all = content_done['quantity_all']['videos']
    tests_all = content_done['quantity_all']['tests']
    practices_all = content_done['quantity_all']['practices']

    def calc_percentage(done, total):
        return int((done / total * 100) if total > 0 else 0)

    return dedent(f"""\
            Ваш прогресс:
            <b>Выполнено тем {topics_done} из {topics_all}, Пройдено {calc_percentage(topics_done, topics_all)}% </b>
            <b>Пройденные Темы:</b>
            {topics_str}
            <b>Выполнено уроков {lessons_done} из {lessons_all}, Пройдено {calc_percentage(lessons_done, lessons_all)}% </b>
            <b>Пройденные Уроки:</b>
            {lessons_str}
            <b>Выполнено видео {videos_done} из {videos_all}, Пройдено {calc_percentage(videos_done, videos_all)}% </b>
            <b>Пройденные Видео:</b>
            {videos_str}
            <b>Выполнено тесты {tests_done} из {tests_all}, Пройдено {calc_percentage(tests_done, tests_all)}% </b>
            <b>Пройденные Тесты:</b>
            {tests_str}
            <b>Выполнено практические задания {practices_done} из {practices_all}, Пройдено {calc_percentage(practices_done,
                                                                                                    practices_all)}% </b>
            <b>Пройденные Практики:</b>
            {practices_str}
        """).replace("  ", "")


def send_content_message(context: CallbackContext, message: str, chat_id: int = None, update: Update = None) -> int:
    """
    Отправляет сообщение с новым контентом и возвращает message_id.
    """
    keyboard = [["📝 Доступные темы", "📖 Главное меню"],
                ["Следующий шаг ➡️"]
                ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    is_callback = bool(update and update.callback_query) if update else False
    return send_message_bot(context, update, message, markup, is_callback, chat_id)


def get_menu_for_role(user_data: dict) -> tuple[str, list[list[str]]]:
    """Возвращает текст сообщения и клавиатуру в зависимости от роли пользователя."""

    user_role = user_data["role"]
    user_contact = user_data["contact"]
    user_tg_name = user_data["tg_name"]

    if user_role in ['admin', 'client']:
        name = user_contact["firstname"] or user_tg_name
        text = dedent(f"""\
            Здравствуй, {name}!

            Давай продолжим изучение хранилища данных (DWH). Ты можешь посмотреть описание всех тем, 
            но доступ к урокам и видео открывается последовательно при прохождении каждого урока и просмотре видео

            Также можешь посмотреть свой тарифный план и срок доступа

            Ну что ж давай уже приступим!!!!
        """)
        keyboard = [["📝 Доступные темы", "🖌 Тариф"],
                    ["🗂 Темы уроков", "🛠 Написать Админу"],
                    ["⤴ Прогресс️"]]
    elif user_contact:
        name = user_contact["firstname"]
        text = dedent(f"""\
            Здравствуйте, {name}!

            Вы можете ознакомиться с курсом, нажав кнопку "🗂 Темы уроков" или стать его участником, 
            нажав кнопку "🧑‍🎓👩‍🎓 Стать клиентом" и выбрав удобный для вас тариф.
        """)
        keyboard = [["🗂 Темы уроков", "🧑‍🎓👩‍🎓 Стать клиентом"],
                    ["🛠 Написать Админу"]
                    ]
    else:
        name = user_tg_name
        text = dedent(f"""\
            Здравствуйте, {name}!

            Вы можете ознакомиться с курсом, нажав кнопку "🗂 Темы уроков" или стать его участником, 
            нажав кнопку "🧑‍🎓👩‍🎓 Стать клиентом" и выбрав удобный для вас тариф.

            А также можете оценить свой уровень как системный аналитик, пройдя тест 
            (для прохождения теста нужно будет зарегистрироваться в боте)
        """)
        keyboard = [["🗂 Темы уроков", "🧑‍🎓👩‍🎓 Стать клиентом"], ["❓ Узнать свой уровень", "🛠 Написать Админу"]]

    return text, keyboard


def start(update: Update, context: CallbackContext) -> States:
    """
    Старт бота: проверяет пользователя в БД, приветствует его или регистрирует нового.
    """
    chat_id = update.message.chat_id
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    if 'prev_message_ids' not in context.user_data:
        context.user_data['prev_message_ids'] = []
    context.user_data['prev_message_ids'].append(update.message.message_id)

    is_callback = bool(update.callback_query)
    if is_callback:
        update.callback_query.answer()
        update.callback_query.delete_message()

    telegram_id = get_telegram_id(update, context)
    context.user_data["telegram_id"] = telegram_id
    response = call_api_get(f"bot/tg_user/{telegram_id}")

    if response.ok:
        user_data = response.json()
        menu_msg, keyboard = get_menu_for_role(user_data)
        context.user_data["user_id"] = user_data["user_id"]
    else:
        username = update.message.from_user.username or update.message.from_user.first_name
        menu_msg = dedent(f"""\
            Привет, {username}!✌️

            Это бот для курса Зайти в ИТ. 
            Здесь вы погрузитесь в атмосферу хранилища данных, SQL, транзакций и т.д.

            Используйте клавиатуру ниже чтобы посмотреть из чего состоит курс, а также можете оценить свой уровень 
            как системный аналитик, пройдя тест (для прохождения теста нужно будет зарегистрироваться в боте)
        """).replace("  ", "")
        keyboard = [["🗂 Темы уроков", "🧑‍🎓👩‍🎓 Стать клиентом"], ["❓ Узнать свой уровень", "🛠 Написать Админу"]]
        payload = {
            "tg_id": telegram_id,
            "tg_name": username,
        }
        try:
            call_api_post("/bot/user/add/", payload)
            logger.info(f"User {telegram_id} added to DB")
        except requests.RequestException as e:
            logger.error(f"Failed to add user {telegram_id}: {str(e)}")

    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    start_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)
    if 'prev_message_ids' not in context.user_data:
        context.user_data['prev_message_ids'] = []
    context.user_data['prev_message_ids'].append(start_message_id)
    return States.TOPICS_MENU


def get_topics_name(update: Update, context: CallbackContext) -> States:
    """Получает название всех тем в курсе и выдает их в качестве кнопок."""
    chat_id = update.message.chat_id
    # Удаляем сообщение пользователя с выбором меню
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    response = call_api_get(f"bot/topics/")
    response.raise_for_status()
    topics = response.json()
    topics_buttons = [topic["title"] for topic in topics]
    topics_buttons.extend(["📖 Главное меню"])
    keyboard = list(chunked(topics_buttons, 2))
    markup = ReplyKeyboardMarkup(keyboard,
                                 resize_keyboard=True,
                                 one_time_keyboard=True)
    menu_msg = dedent("""\
                Выберите интересующую вас тему.
                """)
    is_callback = bool(update.callback_query)
    topic_message = send_message_bot(context, update, menu_msg, markup, is_callback)
    context.user_data['prev_message_ids'].append(topic_message)
    return States.TOPIC


def get_topic_info(update: Update, context: CallbackContext) -> States:
    """Получает информацию о выбранной теме."""
    topic_title = update.message.text
    chat_id = update.message.chat_id

    # Удаляем сообщение пользователя с выбором темы
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    response = call_api_get(f"bot/topic/{topic_title}")
    try:
        response.raise_for_status()
        topic_data = response.json()
        description = clean_html(topic_data['description']) if topic_data['description'] else "Описание отсутствует"

        menu_msg = dedent(f"""\
            <b>Тема:</b>
            {topic_data['title']}

            <b>Описание:</b>
            {description}
        """).replace("  ", "")

        keyboard = [["📖 Главное меню", "🗂 Темы уроков"]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


        if topic_data['picture']:
            logger.info(f"Fetching picture: {topic_data['picture']}")
            try:
                picture_response = requests.get(topic_data['picture'], timeout=10)
                picture_response.raise_for_status()
                photo_message = update.message.reply_photo(
                    photo=picture_response.content,
                    caption=menu_msg,
                    parse_mode=ParseMode.HTML
                )
                context.user_data['prev_message_ids'].append(photo_message.message_id)
            except requests.RequestException as e:
                logger.warning(f"Failed to load picture: {e}")
                text_message = update.message.reply_text(menu_msg, parse_mode=ParseMode.HTML)
                context.user_data['prev_message_ids'].append(text_message.message_id)
        else:
            text_message = update.message.reply_text(menu_msg, parse_mode=ParseMode.HTML)
            context.user_data['prev_message_ids'].append(text_message.message_id)

        menu_message = update.message.reply_text(text='Для возврата выбери тип меню', reply_markup=markup)
        context.user_data['prev_message_ids'].append(menu_message.message_id)
        return States.MAIN_MENU

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def handle_invalid_symbol(update: Update, context: CallbackContext) -> States:
    """Обрабатывает ввод, который не является названием темы."""
    chat_id = update.message.chat_id

    # Удаляем сообщение пользователя
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)

    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    keyboard = [["📖 Главное меню", "🗂 Темы уроков"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    message_id = send_message_bot(
        context, update,
        "☠️Произведен некорректный ввод. Для навигации нужно пользоваться кнопками с названиями ☠️",
        markup,
        is_callback=False
    )

    if 'prev_message_ids' not in context.user_data:
        context.user_data['prev_message_ids'] = []
    context.user_data['prev_message_ids'].append(message_id)

    return States.MAIN_MENU


def message_to_admin(update: Update, context: CallbackContext) -> States:
    message_id = update.message.message_id
    context.user_data['prev_message_ids'].append(message_id)
    menu_msg = 'Напишите вопрос администратору и нажмите отправить'
    message_to_admin = send_message_bot(context, update, menu_msg, markup=None, is_callback=False)
    context.user_data['prev_message_ids'].append(message_to_admin)
    return States.ADMIN


def send_to_admin(update: Update, context: CallbackContext) -> States:
    message_id = update.message.message_id
    context.user_data['prev_message_ids'].append(message_id)
    telegram_id = get_telegram_id(update, context)
    user_fullname = str(update.message.from_user['first_name']) + ' ' + str(update.message.from_user['last_name'])
    message = update.message.text

    menu_msg = dedent(f"""\
                <b>Ваше сообщение отправлено администратору, он свяжется с вами в ближайшее время</b>

                <b>Ваше сообщение:</b>
                {message}
                """).replace("    ", "")
    message_keyboard = [['📖 Главное меню', "🛠 Написать Админу"]]
    markup = ReplyKeyboardMarkup(message_keyboard,
                                 resize_keyboard=True,
                                 one_time_keyboard=True)
    message_to_admin = send_message_bot(context, update, menu_msg, markup, is_callback=False)
    context.user_data['prev_message_ids'].append(message_to_admin)

    # Получаем telegram_id администратора из БД
    response = call_api_get('bot/get_tg_admin')
    try:
        response.raise_for_status()
        admin_data = response.json()
        admin_telegram_id = admin_data['tg_id']
        update.message.chat.id = admin_telegram_id
        menu_msg = dedent(f"""\
                    <b>ИД клиента - ТГ имя:</b>
                    {telegram_id} - {user_fullname}
                    <b>Запрос:</b>
                    {message}
                    <b>Для ответа сначала нажми кнопку "Ответить клиенту"</b>
                    """).replace("    ", "")
        keyboard = [[InlineKeyboardButton(f"Ответить клиенту", callback_data=f"answer_client_{telegram_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_id = context.bot.send_message(
            chat_id=admin_telegram_id,
            text=menu_msg,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML).message_id
        update.message.chat.id = telegram_id
        return States.MAIN_MENU

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        is_callback = bool(update.callback_query)
        keyboard = [['📖 Главное меню', "🛠 Написать Админу"]]
        menu_msg = "Произошла ошибка отправки сообщения администратору напишите ему по номеру телефона +7 980 300 45 45"
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        admin_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'].append(admin_message_id)
        return States.MAIN_MENU


def handle_message_from_client(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    callback_data = query.data
    client_chat_id = callback_data.split('_')[-1]  # Извлекаем ID клиента из callback_data
    context.user_data['client_chat_id'] = client_chat_id

    # Отправляем сообщение администратору с просьбой написать ответ
    message = query.message.reply_text(text='Напиши ответ клиенту и нажми отправить')
    context.user_data['prev_message_ids'].append(message.message_id)
    return States.ADMIN_ANSWER


def send_message_to_user(update, context):
    telegram_id = get_telegram_id(update, context)
    message_from_admin = update.message.text
    message_id = update.message.message_id
    context.user_data['prev_message_ids'].append(message_id)

    admin_name = str(update.message.from_user['first_name'])

    message_to_client = dedent(f"""\
                    <b>Сообщение от {admin_name}</b>

                    <b>Текст сообщение:</b>
                    {message_from_admin}
                    Для ответа администратору нажми кнопку в главном меню
                    """).replace("    ", "")
    update.message.chat.id = context.user_data['client_chat_id']
    admin_message_id = send_message_bot(context, update, message_to_client, markup=None, is_callback=False)
    context.user_data['prev_message_ids'].append(admin_message_id)

    update.message.chat.id = telegram_id
    message_keyboard = [['📖 Главное меню']]

    markup = ReplyKeyboardMarkup(message_keyboard,
                                 resize_keyboard=True,
                                 one_time_keyboard=True)
    menu_msg = 'сообщение отправлено'
    message_to_admin = send_message_bot(context, update, menu_msg, markup, is_callback=False)
    context.user_data['prev_message_ids'].append(message_to_admin)
    return States.MAIN_MENU


def start_registration(update: Update, context: CallbackContext) -> States:
    """Начало сбора регистрационных данных и предлагаем принять оферту об обработке данных."""

    chat_id = update.message.chat_id
    # Удаляем сообщение по нажатию кнопки
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)

    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    message_keyboard = [['✅ Согласен', '❌ Не согласен']]
    markup = ReplyKeyboardMarkup(message_keyboard,
                                 resize_keyboard=True,
                                 one_time_keyboard=True)

    current_dir = os.path.dirname(__file__)
    file_path = os.path.abspath(os.path.join(current_dir, '..', 'media', 'documents', 'privacy_policy_statement.pdf'))

    with open(file_path, 'rb') as image:
        user_agreement_pdf = image.read()

    menu_msg = dedent("""\
    Для того, чтобы пройти тест или провести оплату нужно будет ввести персональные данные (ФИО, номер телефона, e_mail)
     для регистрации, а также согласится на обработку персональных данных

    Это обязательная процедура, пожалуйста, ознакомьтесь с документом.
    """).replace("  ", "")
    document_message = update.message.reply_document(
        user_agreement_pdf,
        filename="Соглашение на обработку персональных данных.pdf",
        caption=menu_msg,
        reply_markup=markup)
    context.user_data['prev_message_ids'] = [document_message.message_id]
    return States.ACCEPT_PRIVACY


def cancel_agreement(update: Update, context: CallbackContext) -> States:
    """ Ответ пользователю, если он не согласен с офертой."""
    chat_id = update.message.chat_id

    # Удаляем сообщение по нажатию кнопки
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    menu_msg = dedent("""
    К сожалению, тогда мы не сможем дать вам возможность пройти тест или провести оплату,
     но вы можете посмотреть описание тем курса, нажав кнопку "🗂 Темы уроков". 
    А вернутся к регистрации сможете в любое время, пройдя по этой ветке.

    Если вы передумали сейчас - нажмите на кнопку согласия ниже.
    """).replace("  ", "")

    keyboard = [['✅ Согласен', '❌ Нет'], ["🗂 Темы уроков"]]

    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    is_callback = bool(update.callback_query)
    agree_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)

    context.user_data['prev_message_ids'].append(agree_message_id)
    return States.ACCEPT_PRIVACY


def start_user_registration(update: Update, context: CallbackContext) -> States:
    """Начало регистрации и сбора данных о пользователе"""
    chat_id = update.message.chat_id

    # Удаляем сообщение по нажатию кнопки
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    menu_msg = dedent("""
        👤 Пожалуйста, напишите свое имя фамилию и город проживания через пробел и нажмите отправить сообщение
        """).replace("  ", "")

    keyboard = [["📖 Главное меню"]]

    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    is_callback = bool(update.callback_query)
    registration_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)

    context.user_data['prev_message_ids'].append(registration_message_id)
    return States.START_REGISTRATION


def get_user_information(update: Update, context: CallbackContext) -> States:
    """
    Записываем информацию о пользователе во временный словарь context.user_data для
    будущей записи в БД.
    """
    message_answer_id = update.message.message_id
    context.user_data['prev_message_ids'].append(message_answer_id)
    words_in_user_answer = len(update.message.text.split())
    if words_in_user_answer != 3:
        incorrect_imput_message = update.message.reply_text(dedent("""\
        Некорректный ввод. Может вы забыли указать фамилию или город?

        Попробуйте еще раз:
        """))
        context.user_data['prev_message_ids'].append(incorrect_imput_message.message_id)
        return States.START_REGISTRATION

    context.user_data["firstname"], context.user_data["secondname"], context.user_data["city"] = update.message.text.split()
    menu_msg = dedent("""
        👤 Пожалуйста, напишите ваш email в формате user@rambler.com и нажмите отправить сообщение
        """).replace("  ", "")
    keyboard = [["🔙 Назад", "📖 Главное меню"]]

    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    is_callback = bool(update.callback_query)
    email_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)

    context.user_data['prev_message_ids'].append(email_message_id)
    return States.USER_EMAIL


def update_email(update: Update, context: CallbackContext) -> States:
    """
    Перезаписываем email при нажатии кнопки Назад на шаге ввода телефонного номера
    """
    message_answer_id = update.message.message_id
    context.user_data['prev_message_ids'].append(message_answer_id)
    menu_msg = dedent("""
        👤 Пожалуйста, напишите ваш email в формате user@rambler.com и нажмите отправить сообщение
        """).replace("  ", "")
    keyboard = [["🔙 Назад", "📖 Главное меню"]]

    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    is_callback = bool(update.callback_query)
    email_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)

    context.user_data['prev_message_ids'].append(email_message_id)
    return States.USER_EMAIL


def get_user_email(update: Update, context: CallbackContext) -> States:
    """
    Записываем email пользователя во временный словарь context.user_data для
    будущей записи в БД.
    """
    message_answer_id = update.message.message_id
    context.user_data['prev_message_ids'].append(message_answer_id)
    context.user_data['user_email'] = update.message.text

    keyboard = [
        [
            KeyboardButton(
                'Отправить свой номер телефона',
                request_contact=True)
        ],
        ["🔙 Назад", "📖 Главное меню"]
    ]
    markup = ReplyKeyboardMarkup(
        keyboard,
        one_time_keyboard=True,
        resize_keyboard=True)

    menu_msg = dedent("""
        📱 Введите ваш номер телефона в формате 
        +7991112233 и нажмите кнопку
        """).replace("  ", "")

    is_callback = bool(update.callback_query)
    phone_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)
    context.user_data['prev_message_ids'].append(phone_message_id)
    return States.USER_PHONE_NUMBER


def send_contact_to_api(update: Update, context: CallbackContext, payload: dict) -> States:
    """Отправляет данные в API и обрабатывает ответ. Идет после get_user_phone_number"""
    try:
        response = call_api_post('/bot/contact/add/', payload)
        if response.ok:
            message_keyboard = [["🧑‍💻 Тест", "Оплата"], ["📖 Главное меню", "🗂 Темы уроков"]]
            markup = ReplyKeyboardMarkup(message_keyboard, resize_keyboard=True, one_time_keyboard=True)
            menu_msg = dedent("""
            🎉 Регистрация прошла успешно!
            Теперь можете приступить к тесту или перейти к оплате, нажав соответствующие кнопки
            """).replace("  ", "")
            is_callback = bool(update.callback_query)
            phone_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)
            context.user_data['prev_message_ids'].append(phone_message_id)
            return States.TEST_LEVEL
        else:
            errors = response.json()
            error_msg = "Ошибка при регистрации:\n"
            if 'email' in errors:
                error_msg += "- Введите корректный email (например, example@example.com)\n"
                message_id = send_message_bot(context, update, error_msg, markup=None, is_callback=False)
                context.user_data['prev_message_ids'].append(message_id)
                return States.USER_EMAIL
            if 'phonenumber' in errors:
                error_msg += "- Введите корректный номер телефона (например, +79991234567)\n"
                message_keyboard = [[KeyboardButton('Отправить свой номер телефона', request_contact=True)]]
                markup = ReplyKeyboardMarkup(message_keyboard, one_time_keyboard=True, resize_keyboard=True)
                message_id = send_message_bot(context, update, error_msg, markup, is_callback=False)
                context.user_data['prev_message_ids'].append(message_id)
                return States.USER_PHONE_NUMBER
            error_msg += f"- Неизвестная ошибка: {errors}"
            message_id = send_message_bot(context, update, error_msg, markup=None, is_callback=False)
            context.user_data['prev_message_ids'].append(message_id)
            return States.MAIN_MENU
    except requests.RequestException as e:
        error_msg = f"Ошибка подключения к серверу: {str(e)}"
        message_id = send_message_bot(context, update, error_msg, markup=None, is_callback=False)
        context.user_data['prev_message_ids'].append(message_id)
        return States.MAIN_MENU


def get_user_phone_number(update: Update, context: CallbackContext) -> int:
    """Получаем и валидируем номер телефона пользователя."""
    message_answer_id = update.message.message_id
    context.user_data.setdefault('prev_message_ids', []).append(message_answer_id)

    # Получаем номер телефона
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text

    is_valid, phone_number = validate_phone_number(phone)
    if not is_valid:
        message_keyboard = [[KeyboardButton('Отправить свой номер телефона', request_contact=True)]]
        markup = ReplyKeyboardMarkup(message_keyboard, one_time_keyboard=True, resize_keyboard=True)
        error_message = dedent("""\
        Введённый номер некорректен. Попробуйте снова (например, +79991234567):
        """)
        message_id = update.message.reply_text(error_message, reply_markup=markup).message_id
        context.user_data['prev_message_ids'].append(message_id)
        return States.USER_PHONE_NUMBER

    context.user_data["phone_number"] = phone_number
    telegram_id = get_telegram_id(update, context)
    response = call_api_get(f"bot/tg_user/{telegram_id}")

    if response.ok:
        user_data = response.json()
        context.user_data["user_id"] = user_data["user_id"]

    payload = {
        "user": context.user_data["user_id"],
        "firstname": context.user_data.get("firstname", ""),
        "secondname": context.user_data.get("secondname", ""),
        "city": context.user_data.get("city", ""),
        "phonenumber": context.user_data["phone_number"],
        "email": context.user_data.get("user_email", "")
    }
    return send_contact_to_api(update, context, payload)


def start_test(update: Update, context: CallbackContext) -> States:
    """Начинает тест."""
    test_title = update.message.text
    chat_id = update.message.chat_id
    if test_title == "Следующий шаг ➡️" or test_title == "🔂 Еще раз":
        test_title = context.user_data.get("test_title")
        if not test_title:
            context.bot.send_message(chat_id=chat_id, text="Ошибка: тест не определён.")
            return States.MAIN_MENU

    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    delete_previous_messages(context, chat_id)

    telegram_id = get_telegram_id(update, context)
    if not telegram_id:
        logger.error("Не удалось получить telegram_id")
        message_id = context.bot.send_message(chat_id=chat_id, text="Ошибка: пользователь не идентифицирован.",
                                              parse_mode=ParseMode.HTML)
        context.user_data['prev_message_ids'] = context.user_data.get('prev_message_ids', []) + [message_id]
        return States.MAIN_MENU

    # Проверяем роль пользователя
    user_role = get_user_role(telegram_id)
    if user_role not in ('admin', 'client'):
        test_title = "Тест уровня"

    response = call_api_get(f'bot/start_test/{test_title}')
    if response.ok:
        test_data = response.json()
        context.user_data['test_title'] = test_title
        context.user_data.update({
            'test_id': test_data['test_id'],
            'questions': test_data['questions'],
            'show_right_answer': test_data['show_right_answer'],
            'current_question_index': 0,
            'correct_answers': 0,
            'prev_message_ids': [],
            'chat_id': chat_id,
            'user_role': user_role,
            'user_id': context.user_data.get('user_id'),
            'telegram_id': telegram_id
        })
        return show_question(chat_id, context)
    else:
        message_id = context.bot.send_message(chat_id=chat_id, text="Тест не найден.", parse_mode=ParseMode.HTML)
        context.user_data['prev_message_ids'] = context.user_data.get('prev_message_ids', []) + [message_id]
        return States.TEST_LEVEL


def show_question(chat_id: int, context: CallbackContext) -> States:
    """Показывает текущий вопрос с вариантами ответа."""
    questions = context.user_data['questions']
    current_question_index = context.user_data['current_question_index']
    prev_message_ids = context.user_data['prev_message_ids']

    """Показывает текущий вопрос с вариантами ответа."""
    if current_question_index >= len(questions):
        return show_test_result(chat_id, context)

    question = questions[current_question_index]
    answers = question['answers']
    answers_text = "\n".join([f"<b>{answer['serial_number']}</b>. {answer['description']}" for answer in answers])
    keyboard = [[str(answer['serial_number']) for answer in answers]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    msg = dedent(f"""
    Вопрос {current_question_index + 1}/{len(questions)}:
    {question['description']}

    Варианты ответа:
    {answers_text}

    <b>Для выбора нескольких ответов укажите номера через запятую БЕЗ ПРОБЕЛА(например, 1,2).</b>
    """).replace("  ", "")

    picture = question.get('picture')
    if picture and isinstance(picture, str) and picture.strip():
        try:
            picture_response = requests.get(picture, timeout=5)
            picture_response.raise_for_status()
            message_id = context.bot.send_photo(
                chat_id=chat_id,
                photo=picture_response.content,
                caption=msg,
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            ).message_id
        except (requests.RequestException, telegram.error.BadRequest) as e:
            print(f"Ошибка загрузки или отправки фото: {e}. Используем текст.")
            message_id = context.bot.send_message(
                chat_id=chat_id,
                text=msg,
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            ).message_id
    else:
        message_id = context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            reply_markup=markup,
            parse_mode=ParseMode.HTML
        ).message_id

    prev_message_ids.append(message_id)
    context.user_data['prev_message_ids'] = prev_message_ids
    return States.TEST_QUESTION


def handle_answer(update: Update, context: CallbackContext) -> States:
    """Обрабатывает ответ пользователя."""
    chat_id = update.message.chat_id
    user_answer = update.message.text
    context.user_data['prev_message_ids'] = context.user_data.get('prev_message_ids', []) + [update.message.message_id]

    if 'questions' not in context.user_data or 'current_question_index' not in context.user_data:
        context.bot.send_message(chat_id=chat_id, text="Ошибка: состояние теста не найдено. Начните тест заново.",
                                 parse_mode=ParseMode.HTML)
        return States.TEST_LEVEL

    questions = context.user_data['questions']
    current_question_index = context.user_data['current_question_index']
    show_right_answer = context.user_data.get('show_right_answer', False)
    correct_answers = context.user_data['correct_answers']
    prev_message_ids = context.user_data['prev_message_ids']

    # Проверяем, завершён ли тест
    if current_question_index >= len(questions):
        context.bot.send_message(chat_id=chat_id, text="Тест уже завершён. Результаты отображены.", parse_mode=ParseMode.HTML)
        delete_previous_messages(context, chat_id, prev_message_ids)
        return States.MAIN_MENU

    question = questions[current_question_index]
    answers = question['answers']

    correct_answers_list = [a for a in answers if a['right']]
    correct_serial_numbers = {str(a['serial_number']) for a in answers if a['right']}

    try:
        user_answers = set(user_answer.split(',')) if user_answer else set()
    except ValueError:
        message_id = context.bot.send_message(chat_id=chat_id,
                                              text="Ошибка: укажите номера ответов через запятую (например, 1,2).",
                                              parse_mode=ParseMode.HTML).message_id
        context.user_data['prev_message_ids'].append(message_id)

        return States.TEST_QUESTION

    if user_answers == correct_serial_numbers:
        correct_answers += 1
        msg = "🎉 Правильно!"
        message_id = context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=None,
                                              parse_mode=ParseMode.HTML).message_id
    else:
        if show_right_answer:
            correct_descriptions = "\n".join([f"{a['serial_number']}. {a['description']}" for a in correct_answers_list])
            msg = f"❌ Неправильно. Правильные ответы:\n{correct_descriptions}"
        else:
            msg = "❌ Неправильно."
        message_id = context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML).message_id

    context.user_data['prev_message_ids'].append(message_id)
    current_question_index += 1

    context.user_data.update({
        'current_question_index': current_question_index,
        'correct_answers': correct_answers,
        'prev_message_ids': prev_message_ids
    })

    return show_question(chat_id, context)


def show_test_result(chat_id: int, context: CallbackContext) -> States:
    """Показывает итоговый результат теста."""
    prev_message_ids = context.user_data.get('prev_message_ids', [])
    delete_previous_messages(context, chat_id, prev_message_ids)

    questions = context.user_data['questions']
    correct_answers = context.user_data['correct_answers']
    user_role = context.user_data['user_role']
    user_id = context.user_data['user_id']
    test_id = context.user_data['test_id']

    total_questions = len(questions)
    percentage = (correct_answers / total_questions) * 100

    if user_role in ('admin', 'client'):
        if percentage >= 80:
            payload = {'user_id': user_id, 'test_id': test_id}
            logger.info(f"Добавление контента: user_id={user_id}, test_id={test_id}")
            logger.info(f"payload: {payload}")
            result = add_content_via_api('/bot/next_content_test/add/', payload, context)
            if not result or result[0] is None:
                logger.error(f"Failed to add content, result: {result}")
                keyboard = [["📝 Доступные темы", "📖 Главное меню"]]
                markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                message_id = context.bot.send_message(
                    chat_id=chat_id,
                    text="Ошибка при добавлении нового контента.",
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML
                ).message_id
                context.user_data['prev_message_ids'].append(message_id)
                return States.MAIN_MENU

            next_content, next_step, next_step_params = result

            # Формируем и отправляем сообщение о новом контенте
            menu_msg = format_content_message(next_content)
            message_id = send_content_message(context, menu_msg, chat_id=chat_id)
            context.user_data['prev_message_ids'].append(message_id)

            logger.info(f"Next step determined: {next_step}, params: {next_step_params}")

            if next_step == 'topic':
                context.user_data['topic_title'] = next_step_params.get('topic_title')
                return States.AVAILABLE_TOPIC
            elif next_step == 'lesson':
                context.user_data['topic_title'] = next_step_params.get('topic_title')
                context.user_data['lesson_title'] = next_step_params.get('lesson_title')
                return States.AVAILABLE_LESSON
            elif next_step == 'video':
                context.user_data['video_title'] = next_step_params.get('video_title')
                context.user_data['lesson_title'] = next_step_params.get('lesson_title')
                return States.AVAILABLE_FINISH_VIDEO
            elif next_step == 'test':
                context.user_data['test_title'] = next_step_params.get('test_title')
                return States.AVAILABLE_FINISH_TEST
            elif next_step == 'practice':
                context.user_data['practice_title'] = next_step_params.get('practice_title')
                context.user_data['lesson_title'] = next_step_params.get('lesson_title')
                return States.AVAILABLE_FINISH_PRACTICE
            else:
                return States.AVAILABLE_FINISH
        else:
            keyboard = [["📝 Доступные темы", "📖 Главное меню"],
                        ["🔂 Еще раз"]]
            markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            message_id = context.bot.send_message(
                chat_id=chat_id,
                text="Тест не пройден. Попробуй ещё раз!",
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            ).message_id
            context.user_data['prev_message_ids'].append(message_id)
            return States.MAIN_MENU

    result_msg = "{:.0f}% правильных ответов - твой результат \n".format(percentage)
    if percentage >= 80:
        result_msg += "🎉 Молодец! Ты набрал более 80% правильных ответов."
    elif percentage >= 50:
        result_msg += "👍 Это нормально! Ты набрал более 50% правильных ответов."
    else:
        result_msg += "📚 Надо подтянуться! Ты набрал менее 50% правильных ответов."

    keyboard = [["📖 Главное меню", "Оплата"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    message_id = context.bot.send_message(
        chat_id=chat_id,
        text=result_msg,
        reply_markup=markup,
        parse_mode=ParseMode.HTML
    ).message_id
    context.user_data['prev_message_ids'] = [message_id]
    return States.TEST_QUESTION


def start_payment(update: Update, context: CallbackContext) -> States:
    """
    Старт оплаты через BotFather и регистрация при в проекте при ее отсутствии
    """
    chat_id = update.message.chat_id
    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    telegram_id = get_telegram_id(update, context)
    response = call_api_get(f"bot/tg_user/{telegram_id}")
    response.raise_for_status()
    user_data = response.json()

    if user_data["contact"] and user_data["contact"]["firstname"] and user_data["contact"]["phonenumber"]:
        name = user_data["contact"]["firstname"]
        menu_msg = dedent(f"""\
                Здравствуйте, {name}!

                Вы уже зарегистрированы в нашем проекте, поэтому можем перейти к выбору тарифа
            """)
        response = call_api_get(f"bot/tariffs/")
        response.raise_for_status()
        tariffs = response.json()
        tariffs_buttons = [tariff["title"] for tariff in tariffs]
        tariffs_buttons.extend(["🗂 Темы уроков"])
        keyboard = list(chunked(tariffs_buttons, 2))
        markup = ReplyKeyboardMarkup(keyboard,
                                     resize_keyboard=True,
                                     one_time_keyboard=True)
        is_callback = bool(update.callback_query)
        registration_message = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'] = [registration_message]
        return States.TARIFF

    else:
        name = user_data["tg_name"]
        menu_msg = dedent(f"""\
                        Здравствуйте, {name}!

                        Перед началом оплаты необходимо зарегистрироваться 
                    """)
        keyboard = [["🗂 Темы уроков", "Регистрация"]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        is_callback = bool(update.callback_query)
        registration_message = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'] = [registration_message]
        return States.ACCEPT_PRIVACY


def get_tariff_info(update: Update, context: CallbackContext) -> States:
    """Получает информацию о выбранном тарифе."""
    tariff_title = update.message.text
    chat_id = update.message.chat_id

    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    response = call_api_get(f"bot/tariff/{tariff_title}")
    try:
        response.raise_for_status()
        tariff_data = response.json()
        description = clean_html(tariff_data['description']) if tariff_data['description'] else "Описание отсутствует"
        context.user_data['tariff_title'] = tariff_data['title']
        context.user_data['tariff_price'] = tariff_data['price']

        menu_msg = dedent(f"""\
            <b>Тариф:</b>
            {tariff_data['title']}

            <b>Описание:</b>
            {description}
            
            <b>Стоимость:</b>
            {tariff_data['price']} руб
        """).replace("  ", "")

        keyboard = [["🔙 Назад", "💵 Оплатить"],
                    ["📖 Главное меню"]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        is_callback = bool(update.callback_query)
        tariff_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'].append(tariff_message_id)
        return States.PAYMENT

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def send_payment(update, context):
    """Отправляет пользователю счёт для оплаты тарифа."""
    message_id = update.message.message_id
    context.user_data['prev_message_ids'].append(message_id)
    logger.info("send_payment called")
    chat_id = update.effective_chat.id
    # Проверяем наличие данных в context.user_data
    try:
        tariff_title = context.user_data['tariff_title']
        tariff_price = int(context.user_data['tariff_price'])  # Преобразуем в int для надёжности
        user_id = context.user_data['user_id']
        logger.info(f"Tariff: {tariff_title}, Price: {tariff_price}, User: {user_id}")
    except (KeyError, ValueError):
        error_message = context.bot.send_message(chat_id=chat_id, text="Ошибка: Не выбран тариф или данные некорректны.")
        context.user_data['prev_message_ids'].append(error_message.message_id)
        logger.error("Invalid tariff data")
        return States.MAIN_MENU

    # Проверяем, что цена положительная
    if tariff_price <= 0:
        error_price = context.bot.send_message(chat_id=chat_id, text="Ошибка: Цена тарифа должна быть положительной.")
        context.user_data['prev_message_ids'].append(error_price.message_id)
        logger.error("Non-positive price")
        return States.MAIN_MENU

    # Минимальный payload
    payload = {
        'u': user_id,
        'a': tariff_price
    }

    payload_str = json.dumps(payload)
    logger.info(f"Payload: {payload_str}")
    context.user_data['last_payload'] = payload_str

    title = f"Оплата тарифа {tariff_title[:20]}"  # Ограничиваем до 32 символов
    description = f"Стоимость заказа - {tariff_price} руб"
    currency = "RUB"
    prices = [LabeledPrice("🖌 Тариф", tariff_price * 100)]

    try:
        invoice = context.bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=payload_str,
            provider_token=provider_ukassa_token,
            currency=currency,
            prices=prices
        )
        if 'prev_message_ids' not in context.user_data:
            context.user_data['prev_message_ids'] = []
        context.user_data['prev_message_ids'].append(invoice.message_id)
        logger.info("Invoice sent successfully")

        # Добавляем кнопку "💵 Оплатить" после инвойса т.к. юкасса не работает
        keyboard = [[InlineKeyboardButton("💵 Оплатить", callback_data="process_payment")],
                    [InlineKeyboardButton("🧾 Отправить чек администратору", callback_data="send_invoice")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message_id = context.bot.send_message(chat_id=chat_id, text="Нажмите кнопку для завершения оплаты:",
                                 reply_markup=reply_markup).message_id
        context.user_data['prev_message_ids'].append(message_id)

    except Exception as e:
        error_invoice = context.bot.send_message(chat_id=chat_id, text=f"Ошибка при создании счёта: {str(e)}")
        context.user_data['prev_message_ids'].append(error_invoice.message_id)
        logger.error(f"Invoice creation failed: {str(e)}")
        return States.MAIN_MENU

    return States.PAYMENT


def precheckout_callback(update: Update, context: CallbackContext) -> None:
    logger.info("precheckout_callback called")
    query = update.pre_checkout_query
    logger.info(f"PreCheckoutQuery payload: {query.invoice_payload}")
    try:
        payload = json.loads(query.invoice_payload)
        if 'u' not in payload or 'a' not in payload:
            logger.error("Missing 'u' or 'a' in payload")
            query.answer(ok=False, error_message="Неверный формат данных.")
        else:
            logger.info("Payload valid, answering OK")
            query.answer(ok=True)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        query.answer(ok=False, error_message="Ошибка в данных оплаты.")


def process_payment(update: Update, context: CallbackContext) -> int:
    logger.info("process_payment called")
    query = update.callback_query
    query.answer()
    return successful_payment(update, context)


def successful_payment(update, context):
    """Обрабатывает успешную оплату."""
    logger.info("successful_payment called")
    chat_id = update.effective_chat.id if update.message else update.callback_query.message.chat_id

    # Используем payload из context.user_data
    payload = json.loads(context.user_data['last_payload'])
    logger.info(f"Payment payload: {payload}")

    today = datetime.now().date()
    one_month_later = today + timedelta(days=30)
    tariff_title = context.user_data['tariff_title']
    full_payload = {
        'amount': payload['a'],
        'user': payload['u'],
        'access_date_start': str(today),
        'access_date_finish': str(one_month_later),
        'tariff': tariff_title,
        'status': "completed",
        'service_description': f"Оплата тарифа {tariff_title}"
    }
    logger.info(f"Full payload for API: {full_payload}")
    try:
        response = call_api_post('/bot/payment/add/', full_payload)
        logger.info(f"API response: {response.status_code}, {response.text}")
        if response.ok:
            payload_content = {
                'user': payload['u'],
                'tariff': tariff_title,
            }
            response_content = call_api_post('/bot/start_content/add/', payload_content)
            response_content.raise_for_status()

            menu_msg = 'Оплата успешно произведена, можете приступать к прохождению курса'
            keyboard = [["📖 Главное меню"]]
            markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

            if 'prev_message_ids' not in context.user_data:
                context.user_data['prev_message_ids'] = []

            is_callback = bool(update.callback_query)
            finish_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)
            context.user_data['prev_message_ids'].append(finish_message_id)
            return States.MAIN_MENU
        else:
            raise requests.RequestException(f"API вернул ошибку: {response.status_code} - {response.text}")

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def send_invoice(update: Update, context: CallbackContext) -> States:
    """Отправляет счет администратору на проверку"""
    menu_msg = dedent(f"""
                    1. Сделайте оплату по присланным реквизитам
                    2. Сохраните чек в виде документа
                    3. Прикрепите файл с чеком к сообщению и нажмите отправить
                    """).replace("  ", "")
    message_to_admin = send_message_bot(context, update, menu_msg, markup=None, is_callback=False)
    context.user_data['prev_message_ids'].append(message_to_admin)
    return States.INVOICE


def send_invoice_to_admin(update: Update, context: CallbackContext) -> States:
    user_fullname = str(update.message.from_user['first_name']) + ' ' + str(update.message.from_user['last_name'])
    file_id = update.message.document.file_id
    file_info = context.bot.get_file(file_id)
    telegram_id = get_telegram_id(update, context)
    menu_msg = dedent(f"""\
                Ваш чек отправлен администратору на проверку,
                 он свяжется с вами после проверки!
                """).replace("    ", "")
    message_keyboard = [['📖 Главное меню']]
    markup = ReplyKeyboardMarkup(message_keyboard,
                                 resize_keyboard=True,
                                 one_time_keyboard=True)
    message_to_admin = send_message_bot(context, update, menu_msg, markup, is_callback=False)
    context.user_data['prev_message_ids'].append(message_to_admin)

    # Получаем telegram_id администратора из БД
    response = call_api_get('bot/get_tg_admin')
    try:
        response.raise_for_status()
        admin_data = response.json()
        admin_telegram_id = admin_data['tg_id']
        update.message.chat.id = admin_telegram_id
        admin_message = dedent(f"""\
                    Чек об оплате от клиента
                    <b>ИД клиента - ТГ имя:</b>
                    {telegram_id} - {user_fullname}
                    <b>Если чек правильный, то откройте клиенту в админке необходимый контент в ручную и 
                    нажми кнопку 'Утвердить'"</b>
                    <b>Если необходимо задать уточняющий вопрос, то нажми кнопку 'Ответить клиенту' и напишите ваши замечания"</b>
                    """).replace("    ", "")

        keyboard = [[InlineKeyboardButton(f"Утвердить", callback_data=f"approve_{telegram_id}")],
                    [InlineKeyboardButton(f"Ответить клиенту", callback_data=f"answer_client_{telegram_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_document(
            chat_id=admin_telegram_id,
            document=file_info.file_id,
            caption=admin_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return States.MAIN_MENU

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        is_callback = bool(update.callback_query)
        keyboard = [['📖 Главное меню', "🛠 Написать Админу"]]
        menu_msg = "Произошла ошибка отправки практического домашнего задания администратору" \
                   " напишите ему по номеру телефона +7 980 300 45 45"
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        admin_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'].append(admin_message_id)
        return States.MAIN_MENU


def get_admin_invoice_approval(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    callback_data = query.data
    telegram_id = get_telegram_id(update, context)  # chat_id администратора

    # Извлекаем информацию из callback_data
    client_chat_id = callback_data.split('_')[-1]

    message_id = query.message.message_id
    context.user_data['prev_message_ids'].append(message_id)

    menu_msg = 'Ответ отправлен пользователю. Нажмите кнопку "📖 Главное меню" или /start'
    keyboard = [["📖 Главное меню"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    message_id = context.bot.send_message(
        chat_id=telegram_id,
        text=menu_msg,
        reply_markup=markup,
        parse_mode=ParseMode.HTML
    )
    context.user_data['prev_message_ids'].append(message_id)

    # Формируем и отправляем сообщение о новом контенте клиенту
    menu_msg = 'Администратор проверил и утвердил вашу оплату. Вам доступны уроки по кнопке "📝 Доступные темы"'
    keyboard = [["📝 Доступные темы", "📖 Главное меню"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    message_id = context.bot.send_message(
        chat_id=client_chat_id,
        text=menu_msg,
        reply_markup=markup,
        parse_mode=ParseMode.HTML
    ).message_id
    context.user_data['prev_message_ids'].append(message_id)
    return States.AVAILABLE_FINISH  # Состояние для администратора


def show_tariff_info(update: Update, context: CallbackContext) -> States:
    """Получает информацию о действующем тарифе."""
    chat_id = update.message.chat_id

    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    telegram_id = get_telegram_id(update, context)
    response = call_api_get(f"bot/tg_user/{telegram_id}")

    try:
        response.raise_for_status()
        user_data = response.json()
        logger.info(f"User info: {user_data }")
        tariff_data = user_data['payments'][-1]
        tariff_title = tariff_data['tariff_detail']['title']
        tariff_price = tariff_data['tariff_detail']['price']
        tariff_description = clean_html(tariff_data['tariff_detail']['description']) if tariff_data[
            'tariff_detail']['description'] else "Описание отсутствует"
        tariff_date_start = tariff_data['access_date_start']
        formatted_tariff_date_start = datetime.strptime(tariff_date_start, '%Y-%m-%d').strftime('%d.%m.%Y')
        tariff_date_finish = tariff_data['access_date_finish']
        formatted_tariff_date_finish = datetime.strptime(tariff_date_finish, '%Y-%m-%d').strftime('%d.%m.%Y')
        user_name = user_data['contact']['firstname']

        menu_msg = dedent(f"""\
            <b>{user_name}, Ваш Тариф:</b>
            {tariff_title}

            <b>Описание:</b>
            {tariff_description}

            <b>Стоимость:</b>
            {tariff_price} руб
            
            <b>Дата начала и окончания действия:</b>
            начало - {formatted_tariff_date_start} 
            окончание - {formatted_tariff_date_finish}
        """).replace("  ", "")

        keyboard = [["🔙 Назад"]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        is_callback = bool(update.callback_query)
        tariff_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'].append(tariff_message_id)
        return States.MAIN_MENU

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def get_available_topics_name(update: Update, context: CallbackContext) -> States:
    """Получает название тем, доступных пользователю и выдает их в качестве кнопок."""
    chat_id = update.message.chat_id
    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    telegram_id = get_telegram_id(update, context)
    response = call_api_get(f"bot/available_topics/{telegram_id}")
    response.raise_for_status()

    availability = response.json()
    topics = availability['topics']
    logger.info(f"Topics for keyboard: {[topic['title'] for topic in topics]}")
    context.user_data['available_lessons'] = availability['lessons']
    topics_buttons = [topic["title"] for topic in topics]
    topics_buttons.extend(["📖 Главное меню"])
    keyboard = list(chunked(topics_buttons, 2))
    markup = ReplyKeyboardMarkup(keyboard,
                                 resize_keyboard=True,
                                 one_time_keyboard=True)
    menu_msg = dedent("""\
                Выберите интересующую вас тему.
                """)
    is_callback = bool(update.callback_query)
    topic_message = send_message_bot(context, update, menu_msg, markup, is_callback)
    context.user_data['prev_message_ids'] = [topic_message]
    return States.AVAILABLE_TOPIC


def get_available_topic_info(update: Update, context: CallbackContext) -> States:
    """Получает информацию о выбранной теме и список уроков в ней"""
    topic_title = update.message.text
    if topic_title == '🔙 Назад' or topic_title == "Следующий шаг ➡️":
        topic_title = context.user_data["topic_title"]
    chat_id = update.message.chat_id

    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    context.user_data["topic_title"] = topic_title

    response = call_api_get(f"bot/topic/{topic_title}")
    try:
        response.raise_for_status()
        topic_data = response.json()
        description = clean_html(topic_data['description']) if topic_data['description'] else "Описание отсутствует"

        response_all_topic_lessons = call_api_get(f"bot/topic_lessons/{topic_title}")
        response_all_topic_lessons.raise_for_status()
        topic_lessons_data = response_all_topic_lessons.json()
        topic_lessons_id = [lesson["lesson_id"] for lesson in topic_lessons_data]

        menu_msg = dedent(f"""\
            <b>Тема:</b>
            {topic_data['title']}

            <b>Описание:</b>
            {description}
        """).replace("  ", "")

        telegram_id = get_telegram_id(update, context)
        response = call_api_get(f"bot/available_topics/{telegram_id}")
        response.raise_for_status()
        availability = response.json()
        topics_buttons = [lesson["title"] for lesson in availability['lessons'] if lesson["lesson_id"] in topic_lessons_id]
        topics_buttons.extend(["📖 Главное меню", "🔙 Назад"])
        keyboard = list(chunked(topics_buttons, 2))
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


        if topic_data['picture']:
            logger.info(f"Fetching picture: {topic_data['picture']}")
            try:
                picture_response = requests.get(topic_data['picture'], timeout=10)
                picture_response.raise_for_status()
                photo_message = update.message.reply_photo(
                    photo=picture_response.content,
                    caption=menu_msg,
                    parse_mode=ParseMode.HTML
                )
                context.user_data['prev_message_ids'].append(photo_message.message_id)
            except requests.RequestException as e:
                logger.warning(f"Failed to load picture: {e}")
                text_message = update.message.reply_text(menu_msg, parse_mode=ParseMode.HTML)
                context.user_data['prev_message_ids'].append(text_message.message_id)
        else:
            text_message = update.message.reply_text(menu_msg, parse_mode=ParseMode.HTML)
            context.user_data['prev_message_ids'].append(text_message.message_id)

        menu_message = update.message.reply_text(text='Выбери доступные уроки', reply_markup=markup)
        context.user_data['prev_message_ids'].append(menu_message.message_id)
        return States.AVAILABLE_LESSON

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def get_lesson_info(update: Update, context: CallbackContext) -> States:
    """Получает информацию о выбранном уроке"""
    lesson_title = update.message.text
    if lesson_title == '🔙 Назад' or lesson_title == "Следующий шаг ➡️":
        lesson_title = context.user_data["lesson_title"]
    chat_id = update.message.chat_id

    topic_title = context.user_data["topic_title"]

    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    response = call_api_get(f"bot/lesson/{topic_title}/{lesson_title}")
    try:
        response.raise_for_status()
        lesson_data = response.json()
        context.user_data["lesson_title"] = lesson_data['title']
        description = clean_html(lesson_data['description']) if lesson_data['description'] else "Описание отсутствует"

        menu_msg = dedent(f"""\
            <b>Урок:</b>
            {lesson_data['title']}

            <b>Описание:</b>
            {description}
        """).replace("  ", "")

        keyboard = [["🎥 Видео уроки", "🧑‍💻 Тесты"],
                   ["Практика", "🔙 Назад"],
                   ["📖 Главное меню"]]

        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        if lesson_data['picture']:
            logger.info(f"Fetching picture: {lesson_data['picture']}")
            try:
                lesson_response = requests.get(lesson_data['picture'])
                lesson_response.raise_for_status()
                photo_message = update.message.reply_photo(
                    photo=lesson_response.content,
                    caption=menu_msg,
                    parse_mode=ParseMode.HTML
                )
                context.user_data['prev_message_ids'].append(photo_message.message_id)
            except requests.RequestException as e:
                logger.warning(f"Failed to load picture: {e}")
                text_message = update.message.reply_text(menu_msg, parse_mode=ParseMode.HTML)
                context.user_data['prev_message_ids'].append(text_message.message_id)

        else:
            text_message = update.message.reply_text(menu_msg, parse_mode=ParseMode.HTML)
            context.user_data['prev_message_ids'].append(text_message.message_id)


        menu_message = update.message.reply_text(text='Начинай с просмотра видео', reply_markup=markup)
        context.user_data['prev_message_ids'].append(menu_message.message_id)
        return States.AVAILABLE_ITEMS

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def get_available_video_title(update: Update, context: CallbackContext) -> States:
    """Получает информацию о доступных видео в выбранном уроке"""
    chat_id = update.message.chat_id
    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    try:
        lesson_title = context.user_data["lesson_title"]
        topic_title = context.user_data["topic_title"]
        response_all_lesson_video = call_api_get(f"bot/lesson_video/{topic_title}/{lesson_title}")
        response_all_lesson_video.raise_for_status()
        lesson_video_data = response_all_lesson_video.json()
        lesson_video_id = [lesson["video_id"] for lesson in lesson_video_data]

        telegram_id = get_telegram_id(update, context)
        response = call_api_get(f"bot/available_topics/{telegram_id}")
        response.raise_for_status()

        availability = response.json()
        videos = availability['videos']
        video_buttons = [video["title"] for video in videos if video["video_id"] in lesson_video_id]
        video_buttons.extend(["📖 Главное меню", "🔙 Назад"])
        keyboard = list(chunked(video_buttons, 2))
        markup = ReplyKeyboardMarkup(keyboard,
                                     resize_keyboard=True,
                                     one_time_keyboard=True)
        menu_msg = dedent("""\
                    Выберите видео. Либо нажмите назад если в этом уроке у вас еще нет доступных видео.
                    """)
        is_callback = bool(update.callback_query)
        video_message = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'] = [video_message]
        return States.AVAILABLE_CONTENT

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def get_video_info(update: Update, context: CallbackContext) -> States:
    """Получает информацию о выбранном видео"""
    video_title = update.message.text
    chat_id = update.message.chat_id

    if video_title == "Следующий шаг ➡️":
        video_title = context.user_data["video_title"]

    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    lesson_title = context.user_data["lesson_title"]
    response = call_api_get(f"bot/video/{lesson_title}/{video_title}")
    try:
        response.raise_for_status()
        video_data = response.json()

        video_link = video_data['video_link']
        context.user_data['video_id'] = video_data['video_id']
        video_message = context.bot.send_message(chat_id=chat_id, text=video_link)
        context.user_data['prev_message_ids'].append(video_message.message_id)

        if not video_data['summaries']:
            description = 'Нет описания'
        else:
            description = video_data['summaries'][0]['description']

        menu_msg = dedent(f"""\
                    <b>Описание:</b>
                    {description}
                """).replace("  ", "")

        keyboard = [["🔙 Назад", "📖 Главное меню"],
                    ["Контрольный вопрос"]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        is_callback = bool(update.callback_query)
        description_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'].append(description_message_id)

        return States.AVAILABLE_QUESTION

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def get_video_control_question(update: Update, context: CallbackContext) -> States:
    """Получаем вопрос для видео."""
    chat_id = update.message.chat_id
    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    video_id = context.user_data['video_id']
    response = call_api_get(f'bot/video_question/{video_id}')
    if response.ok:
        question = response.json()
        context.user_data['current_question'] = question
        answers = question['answers']
        context.user_data["answers"] = answers
        context.user_data["question_id"] = question.get('id')
        answers_text = "\n".join([f"<b>{answer['serial_number']}</b>. {answer['description']}" for answer in answers])
        keyboard = [[str(answer['serial_number']) for answer in answers]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        msg = dedent(f"""
                Вопрос:
                {question['description']}

                Варианты ответа:
                {answers_text}
                """).replace("  ", "")

        picture = question.get('picture')
        if picture and isinstance(picture, str) and picture.strip():
            try:
                picture_response = requests.get(picture, timeout=5)
                picture_response.raise_for_status()
                message_id = context.bot.send_photo(
                    chat_id=chat_id,
                    photo=picture_response.content,
                    caption=msg,
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML
                ).message_id
            except (requests.RequestException, telegram.error.BadRequest) as e:
                logger.error(f"Ошибка загрузки или отправки фото: {e}")
                message_id = context.bot.send_message(
                    chat_id=chat_id,
                    text=msg,
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML
                ).message_id
        else:
            message_id = context.bot.send_message(
                chat_id=chat_id,
                text=msg,
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            ).message_id

        context.user_data['prev_message_ids'].append(message_id)
        return States.AVAILABLE_QUESTION
    else:
        logger.error(f"API error: {response.status_code} - {response.text}")
        keyboard = [["📖 Главное меню"]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        message_id = send_message_bot(context, update, "Вопрос не найден. Обратитесь к администратору", markup, False)
        context.user_data['prev_message_ids'].append(message_id)
        return States.MAIN_MENU


def handle_video_question_answer(update: Update, context: CallbackContext) -> States:
    """Обрабатывает ответ пользователя."""
    chat_id = update.message.chat_id
    user_answer = update.message.text
    context.user_data['prev_message_ids'].append(update.message.message_id)
    answers = context.user_data.get("answers", [])

    correct_answers_list = [a for a in answers if a['right']]
    correct_serial_numbers = [str(a['serial_number']) for a in correct_answers_list]

    if user_answer in correct_serial_numbers:
        msg = "🎉 Правильно!"
        message_id = context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            reply_markup=None,
            parse_mode=ParseMode.HTML
        ).message_id
        context.user_data['prev_message_ids'].append(message_id)
        video_id = context.user_data['video_id']
        telegram_id = get_telegram_id(update, context)
        response = call_api_get(f"bot/tg_user/{telegram_id}")
        if response.ok:
            user_data = response.json()
            user_id = user_data["user_id"]
        else:
            logger.error("User ID not found in context.user_data")
            send_message_bot(context, update, "Ошибка: пользователь не идентифицирован.", None, False)
            return States.MAIN_MENU

        payload = {
            'user_id': user_id,
            'video_id': video_id,
        }
        logger.info(f"payload: {payload}")
        result = add_content_via_api('/bot/next_content/add/', payload, context, update)
        if not result or result[0] is None:  # Проверяем, что результат не None
            logger.error(f"Failed to add content, result: {result}")
            return States.MAIN_MENU

        next_content, next_step, next_step_params = result

        if not next_content:
            # Ошибка уже обработана в add_content_via_api
            return States.MAIN_MENU
        # Формируем и отправляем сообщение о новом контенте
        menu_msg = format_content_message(next_content)
        message_id = send_content_message(context, menu_msg, chat_id=chat_id)
        context.user_data['prev_message_ids'].append(message_id)

        logger.info(f"Next step determined: {next_step}, params: {next_step_params}")

        # Определяем, что доступно пользователю после успешного ответа и отправляем его в соответствующий States
        if next_step == 'topic':
            context.user_data['topic_title'] = next_step_params['topic_title']
            return States.AVAILABLE_TOPIC
        elif next_step == 'lesson':
            context.user_data['topic_title'] = next_step_params['topic_title']
            context.user_data['lesson_title'] = next_step_params['lesson_title']
            return States.AVAILABLE_LESSON
        elif next_step == 'video':
            context.user_data['video_title'] = next_step_params['video_title']
            context.user_data['lesson_title'] = next_step_params['lesson_title']
            return States.AVAILABLE_FINISH_VIDEO
        elif next_step == 'test':
            context.user_data['test_title'] = next_step_params['test_title']
            return States.AVAILABLE_FINISH_TEST
        elif next_step == 'practice':
            context.user_data['practice_title'] = next_step_params['practice_title']
            context.user_data['lesson_title'] = next_step_params['lesson_title']
            return States.AVAILABLE_FINISH_PRACTICE
        else:
            return States.AVAILABLE_FINISH

    else:
        msg = "❌ Неправильно. Попробуй снова"
        message_id = context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML).message_id
        context.user_data['prev_message_ids'].append(message_id)

        time.sleep(1)

        # Повторно отправляем вопрос из сохранённых данных
        question = context.user_data['current_question']
        answers_text = "\n".join([f"<b>{answer['serial_number']}</b>. {answer['description']}" for answer in answers])
        keyboard = [[str(answer['serial_number']) for answer in answers]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        msg = dedent(f"""
                    Вопрос:
                    {question['description']}

                    Варианты ответа:
                    {answers_text}
                    """).replace("  ", "")

        delete_previous_messages(context, chat_id)
        message_id = context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            reply_markup=markup,
            parse_mode=ParseMode.HTML
        ).message_id
        context.user_data['prev_message_ids'].append(message_id)
        return States.AVAILABLE_QUESTION


def get_available_tests_title(update: Update, context: CallbackContext) -> States:
    """Получает информацию о доступных тестах в выбранном уроке"""
    chat_id = update.message.chat_id
    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    try:
        lesson_title = context.user_data["lesson_title"]
        topic_title = context.user_data["topic_title"]
        response_all_lesson_tests = call_api_get(f"bot/lesson_tests/{topic_title}/{lesson_title}")
        response_all_lesson_tests.raise_for_status()
        tests_data = response_all_lesson_tests.json()

        if not tests_data or (isinstance(tests_data, dict) and not tests_data.get('data')):
            logger.info(f"Тесты для урока '{lesson_title}' не найдены")
            keyboard = [["🔙 Назад", "📖 Главное меню"]]
            markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            message_id = send_message_bot(
                context, update,
                "В этом уроке пока нет доступных тестов. Вернитесь назад или в главное меню.",
                markup, False
            )
            context.user_data['prev_message_ids'].append(message_id)
            return States.AVAILABLE_CONTENT

        tests_id = [test["test_id"] for test in tests_data]

        telegram_id = get_telegram_id(update, context)
        response = call_api_get(f"bot/available_topics/{telegram_id}")
        response.raise_for_status()

        availability = response.json()
        tests = availability['tests']
        test_buttons = [test["title"] for test in tests if test["test_id"] in tests_id]
        test_buttons.extend(["📖 Главное меню", "🔙 Назад"])
        keyboard = list(chunked(test_buttons, 2))
        markup = ReplyKeyboardMarkup(keyboard,
                                     resize_keyboard=True,
                                     one_time_keyboard=True)
        menu_msg = dedent("""\
                    Выберите тест. Либо нажмите назад если в этом уроке у вас еще нет доступных тестов.
                    """)
        is_callback = bool(update.callback_query)
        test_message = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'].append(test_message)
        return States.AVAILABLE_CONTENT

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def get_available_practices_title(update: Update, context: CallbackContext) -> States:
    """Получает информацию о доступных практиках в выбранном уроке"""
    chat_id = update.message.chat_id
    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    try:
        lesson_title = context.user_data["lesson_title"]
        topic_title = context.user_data["topic_title"]
        response_all_lesson_practices = call_api_get(f"bot/lesson_practices/{topic_title}/{lesson_title}")
        response_all_lesson_practices.raise_for_status()
        practices_data = response_all_lesson_practices.json()

        if not practices_data or (isinstance(practices_data, dict) and not practices_data.get('data')):
            logger.info(f"Практические задачи для урока '{lesson_title}' не найдены")
            keyboard = [["🔙 Назад", "📖 Главное меню"]]
            markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            message_id = send_message_bot(
                context, update,
                "В этом уроке пока нет доступных практических заданий. Вернитесь назад или в главное меню.",
                markup, False
            )
            context.user_data['prev_message_ids'].append(message_id)
            return States.AVAILABLE_CONTENT

        practices_id = [practice["practice_id"] for practice in practices_data]

        telegram_id = get_telegram_id(update, context)
        response = call_api_get(f"bot/available_topics/{telegram_id}")
        response.raise_for_status()

        availability = response.json()
        practices = availability['practices']
        practice_buttons = [practice["title"] for practice in practices if practice["practice_id"] in practices_id]
        practice_buttons.extend(["📖 Главное меню", "🔙 Назад"])
        keyboard = list(chunked(practice_buttons, 2))
        markup = ReplyKeyboardMarkup(keyboard,
                                     resize_keyboard=True,
                                     one_time_keyboard=True)
        menu_msg = dedent("""\
                    Выберите практическое задание. Либо нажмите назад если в этом уроке у вас еще нет доступных заданий.
                    """)
        is_callback = bool(update.callback_query)
        practice_message = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'].append(practice_message)
        return States.AVAILABLE_CONTENT

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def get_practice_info(update: Update, context: CallbackContext) -> States:
    """Получает информацию о выбранном практическом задании"""
    practice_title = update.message.text
    if practice_title == "Следующий шаг ➡️":
        practice_title = context.user_data["practice_title"]

    context.user_data["practice_title"] = practice_title
    chat_id = update.message.chat_id

    # Удаляем сообщение пользователя с выбором
    context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    lesson_title = context.user_data["lesson_title"]
    response = call_api_get(f"bot/practice/{lesson_title}/{practice_title}")

    try:
        response.raise_for_status()
        practice_data = response.json()
        context.user_data['practice_id'] = practice_data['practice_id']

        practice_exercise = practice_data.get('exercise')
        if not practice_exercise:
            raise ValueError("Exercise file not found or is empty!")
        practice_exercise_response = requests.get(practice_exercise, timeout=5)
        practice_exercise_response.raise_for_status()
        keyboard = [["🔙 Назад", "📖 Главное меню"],
                    ["Отправить ответ на проверку"]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        message_id = context.bot.send_document(
            chat_id=chat_id,
            document=practice_exercise_response.content,
            filename=practice_title,
            caption="Практическое задание",
            reply_markup=markup,
            parse_mode=ParseMode.HTML
        ).message_id
        context.user_data['prev_message_ids'].append(message_id)
        return States.PRACTICE

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN
    except ValueError as e:
        logger.error(f"File error: {str(e)}")
        message = context.bot.send_message(chat_id=chat_id, text="Ошибка: файл задания отсутствует.")
        context.user_data['prev_message_ids'].append(message.message_id)
        handle_api_error(update, context, e, chat_id)
        return States.ADMIN


def send_practice_to_check(update: Update, context: CallbackContext) -> States:
    """Отправляет файл практики ревьюиру на проверку"""
    menu_msg = dedent(f"""
                    1. Сделайте домашнее задание и сохраните его в файле с расширением .doc
                    2. Назовите ваш файл "Название урока - Название практики"
                    3. Прикрепите файл к сообщению и нажмите отправить
                    """).replace("  ", "")
    message_to_admin = send_message_bot(context, update, menu_msg, markup=None, is_callback=False)
    context.user_data['prev_message_ids'].append(message_to_admin)
    return States.PRACTICE


def send_practice_to_admin(update: Update, context: CallbackContext) -> States:
    user_fullname = str(update.message.from_user['first_name']) + ' ' + str(update.message.from_user['last_name'])
    file_id = update.message.document.file_id
    file_info = context.bot.get_file(file_id)
    telegram_id = get_telegram_id(update, context)
    menu_msg = dedent(f"""\
                Ваше домашнее задание отправлено администратору на проверку,
                 он свяжется с вами после проверки!
                """).replace("    ", "")
    message_keyboard = [['📖 Главное меню']]
    markup = ReplyKeyboardMarkup(message_keyboard,
                                 resize_keyboard=True,
                                 one_time_keyboard=True)
    message_to_admin = send_message_bot(context, update, menu_msg, markup, is_callback=False)
    context.user_data['prev_message_ids'].append(message_to_admin)

    # Получаем telegram_id администратора из БД
    response = call_api_get('bot/get_tg_admin')
    try:
        response.raise_for_status()
        admin_data = response.json()
        admin_telegram_id = admin_data['tg_id']
        update.message.chat.id = admin_telegram_id
        lesson_title = context.user_data["lesson_title"]
        practice_title = context.user_data["practice_title"]
        practice_id = context.user_data['practice_id']
        admin_message = dedent(f"""\
                    Домашнее задание от клиента
                    <b>ИД клиента - ТГ имя:</b>
                    {telegram_id} - {user_fullname}
                    <b>Урок - Практика:</b>
                    {lesson_title} - {practice_title}
                    <b>Если ДЗ правильное, то нажми кнопку 'Утвердить' и клиенту откроется следующий контент"</b>
                    <b>Если ДЗ неправильное, то нажми кнопку 'Ответить клиенту' и напишите ваши замечания"</b>
                    """).replace("    ", "")

        keyboard = [[InlineKeyboardButton(f"Утвердить",
                                          callback_data=f"practice_{practice_id}_{telegram_id}")],
                    [InlineKeyboardButton(f"Ответить клиенту", callback_data=f"answer_client_{telegram_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_document(
            chat_id=admin_telegram_id,
            document=file_info.file_id,
            caption=admin_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return States.MAIN_MENU

    except requests.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        is_callback = bool(update.callback_query)
        keyboard = [['📖 Главное меню', "🛠 Написать Админу"]]
        menu_msg = "Произошла ошибка отправки практического домашнего задания администратору" \
                   " напишите ему по номеру телефона +7 980 300 45 45"
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        admin_message_id = send_message_bot(context, update, menu_msg, markup, is_callback)
        context.user_data['prev_message_ids'].append(admin_message_id)
        return States.MAIN_MENU


def not_send_document(update: Update, context: CallbackContext) -> States:
    message_id = update.message.message_id
    context.user_data['prev_message_ids'].append(message_id)
    keyboard = [["🔙 Назад", "📖 Главное меню"],
                ["Отправить ответ на проверку"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    menu_msg = 'Пожалуйста, нажмите на "Отправить ответ на проверку" и прикрепите файл с домашним заданием. \n' \
               'Расширение .doc'
    is_callback = bool(update.callback_query)
    practice_message = send_message_bot(context, update, menu_msg, markup, is_callback)
    context.user_data['prev_message_ids'].append(practice_message)
    return States.PRACTICE


def get_admin_approval(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    callback_data = query.data
    telegram_id = get_telegram_id(update, context)  # chat_id администратора

    # Извлекаем информацию из callback_data
    client_chat_id = callback_data.split('_')[-1]
    practice_id = callback_data.split('_')[-2]

    message_id = query.message.message_id
    context.user_data['prev_message_ids'].append(message_id)

    menu_msg = 'Ответ отправлен пользователю. Нажмите кнопку "📖 Главное меню" или /start'
    keyboard = [["📖 Главное меню"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    message_id = context.bot.send_message(
        chat_id=telegram_id,
        text=menu_msg,
        reply_markup=markup,
        parse_mode=ParseMode.HTML
    )
    context.user_data['prev_message_ids'].append(message_id)

    # Подготовка данных для API
    payload = {
        'practice_id': practice_id,
        'telegram_id': client_chat_id
    }
    next_content, next_step, next_step_params = add_content_via_api('/bot/next_content_practice/add/', payload,
                                                                   context, update)
    if not next_content:
        # Ошибка уже обработана в add_content_via_api
        return States.MAIN_MENU

    # Сохраняем данные клиента во временном хранилище (например, context.bot_data)
    context.bot_data.setdefault('client_updates', {})[client_chat_id] = {
        'next_content': next_content,
        'next_step': next_step,
        'next_step_params': next_step_params
    }

    # Формируем и отправляем сообщение о новом контенте клиенту
    admin_answer = 'Администратор проверил и утвердил ваше домашнее задание \n'
    menu_msg = admin_answer + format_content_message(next_content)

    keyboard = [["📝 Доступные темы", "📖 Главное меню"],
                ["Следующий шаг ➡️"]
                ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    message_id = context.bot.send_message(
        chat_id=client_chat_id,
        text=menu_msg,
        reply_markup=markup,
        parse_mode=ParseMode.HTML
    ).message_id
    context.user_data['prev_message_ids'].append(message_id)

    logger.info(f"Next step determined: {next_step}, params: {next_step_params}")
    return States.AVAILABLE_FINISH  # Состояние для администратора


def get_next_step_after_practice(update: Update, context: CallbackContext) -> States:
    chat_id = update.effective_chat.id
    # Удаляем предыдущие сообщения
    delete_previous_messages(context, chat_id)

    # Получаем сохранённые данные клиента
    client_updates = context.bot_data.get('client_updates', {}).get(str(chat_id))
    if not client_updates:
        context.bot.send_message(chat_id=chat_id, text="Ошибка: данные следующего шага не найдены.", parse_mode=ParseMode.HTML)
        return States.MAIN_MENU

    next_step = client_updates['next_step']
    next_step_params = client_updates['next_step_params']

    # Обновляем context.user_data для клиента
    if next_step == 'topic':
        context.user_data['topic_title'] = next_step_params.get('topic_title')
    elif next_step == 'lesson':
        context.user_data['topic_title'] = next_step_params.get('topic_title')
        context.user_data['lesson_title'] = next_step_params.get('lesson_title')
    elif next_step == 'video':
        context.user_data['video_title'] = next_step_params.get('video_title')
        context.user_data['lesson_title'] = next_step_params.get('lesson_title')
    elif next_step == 'test':
        context.user_data['test_title'] = next_step_params.get('test_title')
    elif next_step == 'practice':
        context.user_data['practice_title'] = next_step_params.get('practice_title')
        context.user_data['lesson_title'] = next_step_params.get('lesson_title')

    menu_msg = "Нажми еще раз Следующий шаг"
    telegram_id = get_telegram_id(update, context)
    keyboard = [["📝 Доступные темы", "📖 Главное меню"],
                ["Следующий шаг ➡️"]
                ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    message_id = context.bot.send_message(
        chat_id=telegram_id,
        text=menu_msg,
        reply_markup=markup,
        parse_mode=ParseMode.HTML
    ).message_id
    context.user_data['prev_message_ids'].append(message_id)

    # Определяем следующее состояние
    if next_step == 'topic':
        return States.AVAILABLE_TOPIC
    elif next_step == 'lesson':
        return States.AVAILABLE_LESSON
    elif next_step == 'video':
        return States.AVAILABLE_FINISH_VIDEO
    elif next_step == 'test':
        return States.AVAILABLE_FINISH_TEST
    elif next_step == 'practice':
        return States.AVAILABLE_FINISH_PRACTICE
    return States.AVAILABLE_FINISH


def user_done_progress(update: Update, context: CallbackContext) -> States:
    """Присылает пользователю информацию по пройденным позициям."""
    chat_id = update.effective_chat.id
    context.user_data['prev_message_ids'].append(update.message.message_id if update.message else None)
    telegram_id = get_telegram_id(update, context)

    try:
        response = call_api_get(f"bot/done_content/{telegram_id}")
        response.raise_for_status()
        done_content = response.json()
        menu_msg = format_done_message(done_content)
    except requests.RequestException as e:
        logger.error(f"Ошибка API: {e}")
        menu_msg = "Не удалось загрузить прогресс. Обратитесь к администратору."

    keyboard = [["📖 Главное меню"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    is_callback = bool(update and update.callback_query) if update else False
    message_id = send_message_bot(context, update, menu_msg, markup, is_callback, chat_id)
    context.user_data['prev_message_ids'].append(message_id)
    return States.MAIN_MENU


if __name__ == '__main__':
    env = environs.Env()
    env.read_env()
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    telegram_bot_token = env.str("TG_BOT_TOKEN")
    provider_ukassa_token = env.str("PAYMENT_UKASSA_TOKEN")

    # Настройка Request с увеличенными таймаутами
    request = Request(connect_timeout=10, read_timeout=30)  # 10 сек на соединение, 30 сек на чтение
    bot = Bot(token=telegram_bot_token, request=request)

    # Создание Updater с настроенным ботом
    updater = Updater(bot=bot, use_context=True)
    dispatcher = updater.dispatcher

    valid_topic_filter = ValidTopicFilter()
    valid_tariff_filter = ValidTariffFilter()
    valid_lesson_filter = ValidLessonFilter()
    valid_video_filter = ValidVideoFilter()
    valid_tests_filter = ValidTestsFilter()
    valid_practices_filter = ValidPracticeFilter()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.TOPICS_MENU: [
                            MessageHandler(
                                Filters.text("🗂 Темы уроков"), get_topics_name
                            ),
                            MessageHandler(
                                Filters.text("📖 Главное меню"), start
                            ),
                            MessageHandler(
                                Filters.text("❓ Узнать свой уровень"), start_registration
                            ),
                            MessageHandler(
                                Filters.text("🧑‍🎓👩‍🎓 Стать клиентом"), start_payment
                            ),
                            MessageHandler(
                                Filters.text("🖌 Тариф"), show_tariff_info
                            ),
                            MessageHandler(
                                Filters.text("📝 Доступные темы"), get_available_topics_name
                            ),
                            MessageHandler(
                                Filters.text("🛠 Написать Админу"), message_to_admin
                            ),
                            MessageHandler(
                                Filters.text("Следующий шаг ➡️"), get_next_step_after_practice
                            ),
                            MessageHandler(
                                Filters.text("⤴ Прогресс️"), user_done_progress
                            ),
                            CallbackQueryHandler(
                                handle_message_from_client, pattern='^answer_client_'
                            ),
                            CallbackQueryHandler(
                                get_admin_approval, pattern='^practice_'
                            ),
                            CallbackQueryHandler(
                                get_admin_invoice_approval, pattern='^approve_'
                            ),
                            MessageHandler(
                                Filters.text, handle_invalid_symbol
                            ),
                        ],
            States.TOPIC: [
                            MessageHandler(
                                Filters.text("📖 Главное меню"), start
                            ),
                            MessageHandler(
                                valid_topic_filter, get_topic_info
                            ),
                            MessageHandler(
                                Filters.text & ~valid_topic_filter, handle_invalid_symbol
                            ),
            ],
            States.MAIN_MENU: [
                            MessageHandler(
                                Filters.text("📖 Главное меню"), start
                            ),
                            MessageHandler(
                                Filters.text("🔙 Назад"), start
                            ),
                            MessageHandler(
                                Filters.text("🗂 Темы уроков"), get_topics_name
                            ),
                            MessageHandler(
                                Filters.text("❓ Узнать свой уровень"), start_registration
                            ),
                            MessageHandler(
                                Filters.text("🛠 Написать Админу"), message_to_admin
                            ),
                            MessageHandler(
                                Filters.text("🔂 Еще раз"), start_test
                            ),
                            MessageHandler(
                                Filters.text("Следующий шаг ➡️"), get_next_step_after_practice
                            ),
                            MessageHandler(
                                Filters.text("⤴ Прогресс️"), user_done_progress
                            ),
                            CallbackQueryHandler(
                                get_admin_approval, pattern='^practice_'
                            ),
                            CallbackQueryHandler(
                                handle_message_from_client, pattern='^answer_client_'
                            ),
                            CallbackQueryHandler(
                                get_admin_invoice_approval, pattern='^approve_'
                            ),
                            MessageHandler(
                                Filters.text, handle_invalid_symbol
                            ),
            ],
            States.ACCEPT_PRIVACY: [
                            MessageHandler(
                                Filters.regex(r'^\s*(✅\s*)?Согласен\s*$'), start_user_registration
                            ),
                            MessageHandler(
                                Filters.regex(r'^\s*(❌\s*)?Не согласен\s*$'), cancel_agreement
                            ),
                            MessageHandler(
                                Filters.text('❌ Нет'), start
                            ),
                            MessageHandler(
                                Filters.text("🗂 Темы уроков"), get_topics_name
                            ),
                            MessageHandler(
                                Filters.text('Регистрация'), start_registration
                            ),
                            MessageHandler(
                                Filters.text, handle_invalid_symbol
                            ),
            ],
            States.START_REGISTRATION: [
                            MessageHandler(
                                Filters.text("📖 Главное меню"), start
                            ),
                            MessageHandler(
                                Filters.text, get_user_information
                            )
            ],
            States.USER_EMAIL: [
                            MessageHandler(
                                Filters.text("📖 Главное меню"), start
                            ),
                            MessageHandler(
                                Filters.text("🔙 Назад"), start_user_registration
                            ),
                            MessageHandler(
                                Filters.text, get_user_email
                )
            ],
            States.USER_PHONE_NUMBER: [
                            MessageHandler(
                                Filters.text("📖 Главное меню"), start
                            ),
                            MessageHandler(
                                Filters.text("🔙 Назад"), update_email
                            ),
                            MessageHandler(
                                Filters.text, get_user_phone_number
                            ),
                            MessageHandler(
                                Filters.contact, get_user_phone_number
                            ),
                            MessageHandler(
                                Filters.text, handle_invalid_symbol
                            ),
            ],
            States.TEST_LEVEL: [
                            MessageHandler(
                                Filters.text("📖 Главное меню"), start
                            ),
                            MessageHandler(
                                Filters.text("🗂 Темы уроков"), get_topics_name
                            ),
                            MessageHandler(
                                Filters.text("🧑‍💻 Тест"), start_test
                            ),
                            MessageHandler(
                                Filters.text("Оплата"), start_payment
                            ),
                            MessageHandler(
                                Filters.text, handle_invalid_symbol
                            ),
            ],
            States.TEST_QUESTION: [
                            MessageHandler(
                                Filters.text("📖 Главное меню"), start
                            ),
                            MessageHandler(
                                Filters.text("📝 Доступные темы"), get_available_topics_name
                            ),
                            MessageHandler(
                                Filters.text("Оплата"), start_payment
                            ),
                            MessageHandler(Filters.text, handle_answer),
            ],
            States.TARIFF: [
                           MessageHandler(
                                Filters.text("🗂 Темы уроков"), get_topics_name
                           ),
                           MessageHandler(
                                valid_tariff_filter, get_tariff_info
                           ),
                            MessageHandler(
                                Filters.text, handle_invalid_symbol
                           ),
            ],
            States.PAYMENT: [
                           MessageHandler(
                                Filters.text("🔙 Назад"), start_payment
                           ),
                           MessageHandler(
                                Filters.text("📖 Главное меню"), start
                           ),
                           MessageHandler(
                                Filters.text("💵 Оплатить"), send_payment
                           ),
                           PreCheckoutQueryHandler(
                                precheckout_callback
                           ),
                           MessageHandler(
                                Filters.successful_payment, successful_payment
                           ),
                           CallbackQueryHandler(
                                process_payment, pattern="process_payment"
                           ),
                            CallbackQueryHandler(
                                send_invoice, pattern="send_invoice"
                            ),
                            MessageHandler(
                                Filters.text, handle_invalid_symbol
                           ),
            ],
            States.AVAILABLE_TOPIC: [
                          MessageHandler(
                                Filters.text("📖 Главное меню"), start
                          ),
                          MessageHandler(
                                Filters.text("Следующий шаг ➡️"), get_available_topic_info
                          ),
                          MessageHandler(
                                valid_topic_filter, get_available_topic_info
                          ),
                          MessageHandler(
                                Filters.text & ~valid_topic_filter, handle_invalid_symbol
                          ),
            ],
            States.AVAILABLE_LESSON: [
                         MessageHandler(
                                Filters.text("📖 Главное меню"), start
                         ),
                        MessageHandler(
                            Filters.text("Следующий шаг ➡️"), get_lesson_info
                        ),
                         MessageHandler(
                                valid_lesson_filter, get_lesson_info
                         ),
                         MessageHandler(
                                Filters.text("🔙 Назад"), get_available_topics_name
                         ),
                         MessageHandler(
                             Filters.text, handle_invalid_symbol
                         ),
            ],
            States.AVAILABLE_ITEMS: [
                        MessageHandler(
                            Filters.text("📖 Главное меню"), start
                        ),
                        MessageHandler(
                            Filters.text("🎥 Видео уроки"), get_available_video_title
                        ),
                        MessageHandler(
                            Filters.text("🧑‍💻 Тесты"), get_available_tests_title
                        ),
                        MessageHandler(
                            Filters.text("🔙 Назад"), get_available_topic_info
                        ),
                        MessageHandler(
                            Filters.text("Практика"), get_available_practices_title
                        ),
                        MessageHandler(
                            Filters.text, handle_invalid_symbol
                        ),
            ],
            States.AVAILABLE_CONTENT: [
                        MessageHandler(
                            Filters.text("📖 Главное меню"), start
                        ),
                        MessageHandler(
                            valid_video_filter, get_video_info
                        ),
                        MessageHandler(
                            valid_tests_filter, start_test
                        ),
                        MessageHandler(
                            valid_practices_filter, get_practice_info
                        ),
                        MessageHandler(
                            Filters.text("🔙 Назад"), get_lesson_info
                        ),
                        MessageHandler(
                            Filters.text, handle_invalid_symbol
                        ),
            ],
            States.AVAILABLE_QUESTION: [
                        MessageHandler(
                            Filters.text("📖 Главное меню"), start
                        ),
                        MessageHandler(
                            Filters.text("🔙 Назад"), get_available_video_title
                        ),
                        MessageHandler(
                            Filters.text("Контрольный вопрос"), get_video_control_question
                        ),
                        MessageHandler(
                            Filters.text, handle_video_question_answer
                        ),
            ],
            States.AVAILABLE_FINISH: [
                        MessageHandler(
                            Filters.text("📖 Главное меню"), start
                        ),
                        MessageHandler(
                            Filters.text("📝 Доступные темы"), get_available_topics_name
                        ),
                    MessageHandler(
                        Filters.text("Следующий шаг ➡️"), get_next_step_after_practice
                    ),
                        MessageHandler(
                            Filters.text, handle_invalid_symbol
                        ),
            ],
            States.AVAILABLE_FINISH_VIDEO: [
                MessageHandler(
                    Filters.text("📖 Главное меню"), start
                ),
                MessageHandler(
                    Filters.text("📝 Доступные темы"), get_available_topics_name
                ),
                MessageHandler(
                    Filters.text("Следующий шаг ➡️"), get_video_info
                ),
                MessageHandler(
                    Filters.text, handle_invalid_symbol
                ),
            ],
            States.AVAILABLE_FINISH_TEST: [
                MessageHandler(
                    Filters.text("📖 Главное меню"), start
                ),
                MessageHandler(
                    Filters.text("📝 Доступные темы"), get_available_topics_name
                ),
                MessageHandler(
                    Filters.text("Следующий шаг ➡️"), start_test
                ),
                MessageHandler(
                    Filters.text, handle_invalid_symbol
                ),
            ],
            States.AVAILABLE_FINISH_PRACTICE: [
                MessageHandler(
                    Filters.text("📖 Главное меню"), start
                ),
                MessageHandler(
                    Filters.text("📝 Доступные темы"), get_available_topics_name
                ),
                MessageHandler(
                    Filters.text("Следующий шаг ➡️"), get_practice_info
                ),
                MessageHandler(
                    Filters.text, handle_invalid_symbol
                ),
            ],
            States.ADMIN: [
                        MessageHandler(
                            Filters.text("📖 Главное меню"), start
                        ),
                        MessageHandler(
                            Filters.text("🛠 Написать Админу"), message_to_admin
                        ),
                        MessageHandler(
                            Filters.text, send_to_admin
                        ),
            ],
            States.ADMIN_ANSWER: [
                        CallbackQueryHandler(
                            handle_message_from_client, pattern='^answer_client_'
                        ),
                        CallbackQueryHandler(
                            get_admin_approval, pattern='^practice_'
                        ),
                        CallbackQueryHandler(
                            get_admin_invoice_approval, pattern='^approve_'
                        ),
                        MessageHandler(
                            Filters.text, send_message_to_user
                        ),
            ],
            States.PRACTICE: [
                        MessageHandler(
                            Filters.text("📖 Главное меню"), start
                        ),
                        MessageHandler(
                            Filters.text("🔙 Назад"), get_available_practices_title
                        ),
                        MessageHandler(
                            Filters.text("Отправить ответ на проверку"), send_practice_to_check
                        ),
                        MessageHandler(
                            Filters.text("Следующий шаг ➡️"), get_next_step_after_practice
                        ),
                        MessageHandler(
                            Filters.document, send_practice_to_admin
                        ),
                        MessageHandler(
                            Filters.photo, not_send_document
                        ),
                        MessageHandler(
                            Filters.text, not_send_document
                        ),
            ],
            States.INVOICE: [
                MessageHandler(
                    Filters.text("📖 Главное меню"), start
                ),
                MessageHandler(
                    Filters.document, send_invoice_to_admin
                ),
                MessageHandler(
                    Filters.photo, not_send_document
                ),
                MessageHandler(
                    Filters.text, not_send_document
                ),
            ]
        },
        fallbacks=[],
        allow_reentry=True,
        name='bot_conversation',
        per_message=False,
    )

    # Добавление обработчика ошибок
    def error_handler(update: Update, context: CallbackContext):
        """Обработчик ошибок."""
        logger.error(f"Update {update} caused error {context.error}")
        if isinstance(context.error, telegram.error.TimedOut):
            update.message.reply_text(
                "⏳ Произошла ошибка из-за медленного интернета. Пожалуйста, попробуйте снова."
            )
        else:
            update.message.reply_text(
                "❌ Произошла ошибка. Пожалуйста, попробуйте снова или свяжитесь с поддержкой."
            )


    dispatcher.add_error_handler(error_handler)
    dispatcher.add_handler(conv_handler)
    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)

    updater.start_polling()
    updater.idle()


# PAYMENT_UKASSA_TOKEN='381764678:TEST:55794'