import os
import random
import logging
import sys
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Хранилища данных
user_sessions = {}
user_stats = defaultdict(lambda: {'total': 0, 'correct': 0, 'details': {}})

def generate_question(mode, number=None):
    if mode == 'all':
        a = random.randint(2, 9)
        b = random.randint(2, 9)
        return (a, b), a * b
    else:
        b = random.randint(2, 9)
        return (number, b), number * b

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔢 Выбрать число", callback_data="select_number")],
        [InlineKeyboardButton("📚 Вся таблица", callback_data="mode_all")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("❌ Завершить", callback_data="end")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_number_keyboard():
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
    keyboard = [
        [InlineKeyboardButton("✅ Следующий вопрос", callback_data="next")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context):
    user_id = update.effective_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    await update.message.reply_text(
        "🎓 *Добро пожаловать в тренажёр таблицы умножения!*\n\nВыбери режим:",
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        if user_id in user_sessions:
            del user_sessions[user_id]
        await query.edit_message_text("🏠 *Главное меню*", reply_markup=get_main_keyboard(), parse_mode='Markdown')
    elif data == "select_number":
        await query.edit_message_text("🔢 *Выберите число* от 2 до 9:", reply_markup=get_number_keyboard(), parse_mode='Markdown')
    elif data == "mode_all":
        user_sessions[user_id] = {'mode': 'all', 'attempts': 0}
        question, answer = generate_question('all')
        user_sessions[user_id].update({'current_question': question, 'correct_answer': answer})
        await query.edit_message_text(f"📚 *Вся таблица*\n❓ {question[0]} × {question[1]} = ?\n(3 попытки)", reply_markup=get_continue_keyboard(), parse_mode='Markdown')
    elif data.startswith("number_"):
        num = int(data.split("_")[1])
        user_sessions[user_id] = {'mode': 'number', 'current_number': num, 'attempts': 0}
        question, answer = generate_question('number', num)
        user_sessions[user_id].update({'current_question': question, 'correct_answer': answer})
        await query.edit_message_text(f"🔢 *Таблица на {num}*\n❓ {question[0]} × {question[1]} = ?\n(3 попытки)", reply_markup=get_continue_keyboard(), parse_mode='Markdown')
    elif data == "stats":
        s = user_stats[user_id]
        acc = (s['correct']/s['total']*100) if s['total']>0 else 0
        text = f"📊 *Статистика*\nВсего: {s['total']}\n✅ {s['correct']} ({acc:.1f}%)"
        if s['details']:
            text += "\n\n*По числам:*\n" + "\n".join(f"{n}: {d['correct']}/{d['total']} ({d['correct']/d['total']*100:.0f}%)" for n,d in sorted(s['details'].items()))
        await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode='Markdown')
    elif data == "end":
        if user_id in user_sessions:
            del user_sessions[user_id]
        await query.edit_message_text("👋 До встречи! /start", reply_markup=None)
    elif data == "next":
        if user_id not in user_sessions:
            await query.edit_message_text("Начни с /start", reply_markup=None)
            return
        ses = user_sessions[user_id]
        ses['attempts'] = 0
        if ses['mode'] == 'all':
            q,a = generate_question('all')
        else:
            q,a = generate_question('number', ses['current_number'])
        ses.update({'current_question': q, 'correct_answer': a})
        mode_text = "Вся таблица" if ses['mode']=='all' else f"Таблица на {ses['current_number']}"
        await query.edit_message_text(f"📚 *{mode_text}*\n❓ {q[0]} × {q[1]} = ?\n(3 попытки)", reply_markup=get_continue_keyboard(), parse_mode='Markdown')

async def handle_answer(update: Update, context):
    uid = update.effective_user.id
    if uid not in user_sessions:
        await update.message.reply_text("Выбери режим: /start", reply_markup=get_main_keyboard())
        return
    try:
        ans = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Введи число!")
        return
    ses = user_sessions[uid]
    ses['attempts'] += 1
    num = ses['current_number'] if ses['mode']=='number' else ses['current_question'][0]
    if ans == ses['correct_answer']:
        user_stats[uid]['total'] += 1
        user_stats[uid]['correct'] += 1
        user_stats[uid]['details'].setdefault(num, {'total':0,'correct':0})
        user_stats[uid]['details'][num]['total'] += 1
        user_stats[uid]['details'][num]['correct'] += 1
        await update.message.reply_text(f"✅ Правильно! {ses['current_question'][0]}×{ses['current_question'][1]}={ses['correct_answer']}\n\nДальше:", reply_markup=get_continue_keyboard(), parse_mode='Markdown')
        ses['attempts'] = 0
    else:
        if ses['attempts'] < 3:
            await update.message.reply_text(f"❌ Неверно. Осталось {3-ses['attempts']} попытки.\n{ses['current_question'][0]} × {ses['current_question'][1]} = ?", parse_mode='Markdown')
        else:
            user_stats[uid]['total'] += 1
            user_stats[uid]['details'].setdefault(num, {'total':0,'correct':0})
            user_stats[uid]['details'][num]['total'] += 1
            await update.message.reply_text(f"😔 Попытки кончились. Ответ: {ses['current_question'][0]}×{ses['current_question'][1]}={ses['correct_answer']}\n\nДальше:", reply_markup=get_continue_keyboard(), parse_mode='Markdown')
            ses['attempts'] = 0

def main():
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ ОШИБКА: переменная TELEGRAM_BOT_TOKEN не установлена!")
        sys.exit(1)
    print("✅ Токен найден, запускаем бота...")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))
    print("🚀 Бот запущен и слушает сообщения...")
    app.run_polling()

if __name__ == '__main__':
    main()
