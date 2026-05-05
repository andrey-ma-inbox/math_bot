import os
import random
import logging
from datetime import datetime
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ConversationHandler
)
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_ANSWER = 1

# Хранилище данных пользователей
user_sessions = {}  # {user_id: {'mode': 'number'/'all', 'current_number': int, 'current_question': tuple, 'attempts': int}}
user_stats = defaultdict(lambda: {'total': 0, 'correct': 0, 'details': {}})  # Статистика

def generate_question(mode, number=None):
    """Генерирует вопрос в зависимости от режима"""
    if mode == 'all':
        a = random.randint(2, 9)
        b = random.randint(2, 9)
        return (a, b), a * b
    else:  # конкретное число
        b = random.randint(2, 9)
        return (number, b), number * b

def get_main_keyboard():
    """Главное меню с кнопками"""
    keyboard = [
        [InlineKeyboardButton("🔢 Выбрать число", callback_data="select_number")],
        [InlineKeyboardButton("📚 Вся таблица", callback_data="mode_all")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("❌ Завершить", callback_data="end")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_number_keyboard():
    """Клавиатура с числами от 2 до 9"""
    keyboard = []
    row = []
    for i in range(2, 10):
        row.append(InlineKeyboardButton(str(i), callback_data=f"number_{i}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_continue_keyboard():
    """Клавиатура для продолжения или выхода"""
    keyboard = [
        [InlineKeyboardButton("✅ Следующий вопрос", callback_data="next")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    await update.message.reply_text(
        "🎓 *Добро пожаловать в тренажёр таблицы умножения!*\n\n"
        "Я помогу тебе выучить таблицу умножения от 2 до 9.\n"
        "Выбери режим обучения:",
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "main_menu":
        if user_id in user_sessions:
            del user_sessions[user_id]
        await query.edit_message_text(
            "🏠 *Главное меню*\n\nВыберите режим:",
            reply_markup=get_main_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    elif data == "select_number":
        await query.edit_message_text(
            "🔢 *Выберите число* от 2 до 9:",
            reply_markup=get_number_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    elif data == "mode_all":
        # Режим "Вся таблица"
        user_sessions[user_id] = {
            'mode': 'all',
            'current_number': None,
            'attempts': 0,
            'conversation_active': True
        }
        question, correct_answer = generate_question('all')
        user_sessions[user_id]['current_question'] = question
        user_sessions[user_id]['correct_answer'] = correct_answer
        user_sessions[user_id]['attempts'] = 0
        
        await query.edit_message_text(
            f"📚 *Режим: Вся таблица*\n\n"
            f"❓ Сколько будет *{question[0]} × {question[1]}* ?\n\n"
            f"У тебя 3 попытки. Напиши ответ числом:",
            reply_markup=get_continue_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    elif data.startswith("number_"):
        # Выбрано конкретное число
        number = int(data.split("_")[1])
        user_sessions[user_id] = {
            'mode': 'number',
            'current_number': number,
            'attempts': 0,
            'conversation_active': True
        }
        question, correct_answer = generate_question('number', number)
        user_sessions[user_id]['current_question'] = question
        user_sessions[user_id]['correct_answer'] = correct_answer
        
        await query.edit_message_text(
            f"🔢 *Таблица умножения на {number}*\n\n"
            f"❓ Сколько будет *{question[0]} × {question[1]}* ?\n\n"
            f"У тебя 3 попытки. Напиши ответ числом:",
            reply_markup=get_continue_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    elif data == "stats":
        # Показ статистики
        stats = user_stats[user_id]
        total = stats['total']
        correct = stats['correct']
        accuracy = (correct / total * 100) if total > 0 else 0
        
        stats_text = f"📊 *Ваша статистика*\n\n"
        stats_text += f"Всего ответов: *{total}*\n"
        stats_text += f"Правильных: *{correct}*\n"
        stats_text += f"Точность: *{accuracy:.1f}%*\n\n"
        
        if stats['details']:
            stats_text += "*По числам:*\n"
            for num in sorted(stats['details'].keys()):
                d = stats['details'][num]
                acc = (d['correct'] / d['total'] * 100) if d['total'] > 0 else 0
                stats_text += f"На {num}: {d['correct']}/{d['total']} ({acc:.0f}%)\n"
        
        await query.edit_message_text(
            stats_text,
            reply_markup=get_main_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    elif data == "end":
        if user_id in user_sessions:
            del user_sessions[user_id]
        await query.edit_message_text(
            "👋 *До свидания!*\n\n"
            "Чтобы начать заново, отправь /start",
            reply_markup=None,
            parse_mode='Markdown'
        )
        return
    
    elif data == "next":
        # Следующий вопрос
        if user_id not in user_sessions:
            await query.edit_message_text(
                "Начни сначала командой /start",
                reply_markup=None
            )
            return
        
        session = user_sessions[user_id]
        session['attempts'] = 0
        
        if session['mode'] == 'all':
            question, correct_answer = generate_question('all')
        else:
            question, correct_answer = generate_question('number', session['current_number'])
        
        session['current_question'] = question
        session['correct_answer'] = correct_answer
        
        mode_text = "Вся таблица" if session['mode'] == 'all' else f"Таблица на {session['current_number']}"
        
        await query.edit_message_text(
            f"📚 *{mode_text}*\n\n"
            f"❓ Сколько будет *{question[0]} × {question[1]}* ?\n\n"
            f"У тебя 3 попытки. Напиши ответ числом:",
            reply_markup=get_continue_keyboard(),
            parse_mode='Markdown'
        )
        return

async def handle_answer(update: Update, context):
    """Обработка ответа пользователя"""
    user_id = update.effective_user.id
    user_answer_text = update.message.text.strip()
    
    # Проверяем, активна ли сессия
    if user_id not in user_sessions:
        await update.message.reply_text(
            "Сначала выбери режим через /start",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Проверяем, что введено число
    try:
        user_answer = int(user_answer_text)
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введи число!")
        return
    
    session = user_sessions[user_id]
    correct_answer = session['correct_answer']
    session['attempts'] += 1
    
    # Обновляем статистику
    if session['mode'] == 'number':
        current_num = session['current_number']
    else:
        # Для режима "вся таблица" сохраняем статистику по первому числу
        current_num = session['current_question'][0]
    
    if user_answer == correct_answer:
        # Правильный ответ
        user_stats[user_id]['total'] += 1
        user_stats[user_id]['correct'] += 1
        
        if current_num not in user_stats[user_id]['details']:
            user_stats[user_id]['details'][current_num] = {'total': 0, 'correct': 0}
        user_stats[user_id]['details'][current_num]['total'] += 1
        user_stats[user_id]['details'][current_num]['correct'] += 1
        
        await update.message.reply_text(
            f"✅ *Правильно!* {session['current_question'][0]} × {session['current_question'][1]} = {correct_answer}\n\n"
            f"Нажми кнопку для следующего вопроса:",
            reply_markup=get_continue_keyboard(),
            parse_mode='Markdown'
        )
        # Сброс попыток для следующего вопроса
        session['attempts'] = 0
    else:
        # Неправильный ответ
        if session['attempts'] < 3:
            await update.message.reply_text(
                f"❌ *Неправильно!* Осталось попыток: {3 - session['attempts']}\n"
                f"Попробуй ещё раз: *{session['current_question'][0]} × {session['current_question'][1]}* = ?",
                parse_mode='Markdown'
            )
        else:
            # Три попытки исчерпаны
            user_stats[user_id]['total'] += 1
            if current_num not in user_stats[user_id]['details']:
                user_stats[user_id]['details'][current_num] = {'total': 0, 'correct': 0}
            user_stats[user_id]['details'][current_num]['total'] += 1
            
            await update.message.reply_text(
                f"😔 *Попытки закончились!*\n"
                f"Правильный ответ: *{session['current_question'][0]} × {session['current_question'][1]} = {correct_answer}*\n\n"
                f"Нажми кнопку для следующего вопроса:",
                reply_markup=get_continue_keyboard(),
                parse_mode='Markdown'
            )
            session['attempts'] = 0

async def cancel(update: Update, context):
    """Отмена и выход"""
    user_id = update.effective_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    await update.message.reply_text(
        "👋 Сессия завершена. Для начала используй /start"
    )

def main():
    """Запуск бота"""
    # Токен из переменной окружения
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
        return
    
    # Создаём приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Запускаем бота
    print("✅ Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()