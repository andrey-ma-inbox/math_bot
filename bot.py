import os
import random
import logging
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилища
user_sessions = {}
user_stats = defaultdict(lambda: {'total': 0, 'correct': 0, 'details': {}})

def generate_question(mode, number=None):
    if mode == 'all':
        a, b = random.randint(2, 9), random.randint(2, 9)
    else:
        a, b = number, random.randint(2, 9)
    return (a, b), a * b

def get_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔢 Выбрать число", callback_data="select_number")],
        [InlineKeyboardButton("📚 Вся таблица", callback_data="mode_all")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("❌ Завершить", callback_data="end")]
    ])

def get_number_keyboard():
    keyboard = []
    for i in range(2, 10):
        keyboard.append([InlineKeyboardButton(str(i), callback_data=f"num_{i}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def get_continue_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Следующий вопрос", callback_data="next")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ])

async def start(update: Update, context):
    user_id = update.effective_user.id
    user_sessions.pop(user_id, None)
    await update.message.reply_text(
        "🎓 *Таблица умножения*\n\nВыбери режим:",
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "main_menu":
        user_sessions.pop(user_id, None)
        await query.edit_message_text("🏠 *Главное меню*", reply_markup=get_main_keyboard(), parse_mode='Markdown')

    elif data == "select_number":
        await query.edit_message_text("🔢 *Выбери число:*", reply_markup=get_number_keyboard(), parse_mode='Markdown')

    elif data == "mode_all":
        q, a = generate_question('all')
        user_sessions[user_id] = {'mode': 'all', 'question': q, 'answer': a, 'attempts': 0}
        await query.edit_message_text(f"📚 *Вся таблица*\n\n❓ {q[0]} × {q[1]} = ?\n(3 попытки)", reply_markup=get_continue_keyboard(), parse_mode='Markdown')

    elif data.startswith("num_"):
        num = int(data.split('_')[1])
        q, a = generate_question('number', num)
        user_sessions[user_id] = {'mode': 'number', 'num': num, 'question': q, 'answer': a, 'attempts': 0}
        await query.edit_message_text(f"🔢 *Таблица на {num}*\n\n❓ {q[0]} × {q[1]} = ?\n(3 попытки)", reply_markup=get_continue_keyboard(), parse_mode='Markdown')

    elif data == "stats":
        s = user_stats[user_id]
        acc = (s['correct']/s['total']*100) if s['total']>0 else 0
        text = f"📊 *Статистика*\nВсего: {s['total']}\nПравильно: {s['correct']} ({acc:.1f}%)"
        if s['details']:
            text += "\n\n*По числам:*\n" + "\n".join(f"{n}: {d['correct']}/{d['total']}" for n,d in sorted(s['details'].items()))
        await query.edit_message_text(text, reply_markup=get_main_keyboard(), parse_mode='Markdown')

    elif data == "end":
        user_sessions.pop(user_id, None)
        await query.edit_message_text("👋 Пока! Для начала отправь /start")

    elif data == "next":
        if user_id not in user_sessions:
            await query.edit_message_text("Начни с /start", reply_markup=None)
            return
        ses = user_sessions[user_id]
        ses['attempts'] = 0
        if ses['mode'] == 'all':
            q, a = generate_question('all')
        else:
            q, a = generate_question('number', ses['num'])
        ses['question'], ses['answer'] = q, a
        mode = "Вся таблица" if ses['mode'] == 'all' else f"Таблица на {ses['num']}"
        await query.edit_message_text(f"📚 *{mode}*\n\n❓ {q[0]} × {q[1]} = ?\n(3 попытки)", reply_markup=get_continue_keyboard(), parse_mode='Markdown')

async def handle_answer(update: Update, context):
    uid = update.effective_user.id
    if uid not in user_sessions:
        await update.message.reply_text("Выбери режим: /start", reply_markup=get_main_keyboard())
        return

    try:
        answer = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Введи число!")
        return

    ses = user_sessions[uid]
    ses['attempts'] += 1
    num = ses['num'] if ses['mode'] == 'number' else ses['question'][0]

    if answer == ses['answer']:
        # Правильно
        user_stats[uid]['total'] += 1
        user_stats[uid]['correct'] += 1
        user_stats[uid]['details'].setdefault(num, {'total':0, 'correct':0})
        user_stats[uid]['details'][num]['total'] += 1
        user_stats[uid]['details'][num]['correct'] += 1

        await update.message.reply_text(
            f"✅ *Правильно!* {ses['question'][0]} × {ses['question'][1]} = {ses['answer']}\n\nСледующий вопрос:",
            reply_markup=get_continue_keyboard(),
            parse_mode='Markdown'
        )
        ses['attempts'] = 0
    else:
        if ses['attempts'] < 3:
            await update.message.reply_text(
                f"❌ *Неверно!* Осталось {3 - ses['attempts']} попытки.\n\n{ses['question'][0]} × {ses['question'][1]} = ?",
                parse_mode='Markdown'
            )
        else:
            # 3 попытки истрачено
            user_stats[uid]['total'] += 1
            user_stats[uid]['details'].setdefault(num, {'total':0, 'correct':0})
            user_stats[uid]['details'][num]['total'] += 1

            await update.message.reply_text(
                f"😔 *Попытки кончились!*\nПравильный ответ: {ses['question'][0]} × {ses['question'][1]} = {ses['answer']}\n\nСледующий вопрос:",
                reply_markup=get_continue_keyboard(),
                parse_mode='Markdown'
            )
            ses['attempts'] = 0

def main():
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не задан!")
        return

    print("✅ Токен найден, запускаем бота...")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))
    print("🚀 Бот успешно запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
