from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from datetime import datetime, timezone, timedelta
from persiantools.jdatetime import JalaliDateTime
import asyncio
import json
import re
import os

# Conversation states
WAITING_FOR_LINK = 1
WAITING_FOR_TIME = 2

# JSON file to store countdown data
DB_FILE = 'countdowns.json'

def load_countdowns():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_countdowns(countdowns):
    with open(DB_FILE, 'w') as f:
        json.dump(countdowns, f)

def extract_message_info(message_link):
    pattern = r'https://t\.me/(?:c/(\d+)|([^/]+))/(\d+)'
    match = re.match(pattern, message_link)
    
    if not match:
        return None
        
    chat_id = match.group(1) or match.group(2)
    message_id = int(match.group(3))
    
    # If numeric chat_id (private channel), add -100 prefix
    if chat_id.isdigit():
        chat_id = int(f"-100{chat_id}")
    
    return chat_id, message_id

def remaining_time_from_timestamp(target_timestamp):
    current_time = datetime.now()
    target_time = datetime.fromtimestamp(target_timestamp)
    
    remaining_time = target_time - current_time
    
    if remaining_time.total_seconds() <= 0:
        return None
    
    remaining_days = remaining_time.days
    remaining_hours, remainder = divmod(remaining_time.seconds, 3600)
    remaining_minutes, remaining_seconds = divmod(remainder, 60)
    
    return remaining_days, remaining_hours, remaining_minutes, remaining_seconds

def format_countdown_message(remaining_time):
    if remaining_time is None:
        return " زمان به پایان رسید!"
        
    days, hours, minutes, seconds = remaining_time
    return f"زمان باقی مانده: {days} روز, {hours} ساعت, {minutes} دقیقه, {seconds} ثانیه"

async def update_single_countdown(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, target_timestamp: float) -> None:
    countdown_key = f"{chat_id}_{message_id}"
    
    try:
        remaining_time = remaining_time_from_timestamp(target_timestamp)
        message_text = format_countdown_message(remaining_time)
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=message_text
        )
        
        if remaining_time is None:
            # Time's up, stop the countdown
            countdowns = load_countdowns()
            if countdown_key in countdowns:
                del countdowns[countdown_key]
                save_countdowns(countdowns)
            # Remove the job
            current_jobs = context.job_queue.get_jobs_by_name(countdown_key)
            for job in current_jobs:
                job.schedule_removal()
            return
            
    except Exception as e:
        print(f"Error updating countdown {countdown_key}: {e}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=" خطا در بروزرسانی پیام شمارش معکوس. لطفاً مطمئن شوید که ربات ادمین کانال است."
            )
        except:
            pass
        # Remove the failed countdown
        countdowns = load_countdowns()
        if countdown_key in countdowns:
            del countdowns[countdown_key]
            save_countdowns(countdowns)
        # Remove the job
        current_jobs = context.job_queue.get_jobs_by_name(countdown_key)
        for job in current_jobs:
            job.schedule_removal()

def create_countdown_job(application: Application, chat_id: int, message_id: int, target_timestamp: float) -> None:
    """Create a new job for a countdown"""
    countdown_key = f"{chat_id}_{message_id}"
    
    # Remove any existing jobs for this countdown
    current_jobs = application.job_queue.get_jobs_by_name(countdown_key)
    for job in current_jobs:
        job.schedule_removal()
    
    # Create new job
    application.job_queue.run_repeating(
        callback=lambda context: update_single_countdown(context, chat_id, message_id, target_timestamp),
        interval=10,  # Update every 10 seconds
        first=1,  # Start after 1 second
        name=countdown_key
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    instructions = (
        " سلام! من یک ربات شمارش معکوس هستم.\n\n"
        "برای استفاده از من در کانال خود، لطفا مراحل زیر را دنبال کنید:\n"
        "1️⃣ من را به کانال خود اضافه کنید\n"
        "2️⃣ من را به عنوان ادمین کانال تنظیم کنید\n"
        "3️⃣ یک پیام در کانال ارسال کنید و لینک پیام را کپی کنید\n"
        "4️⃣ دستور /add_countdown را ارسال کنید و لینک پیام را برای من بفرستید\n"
        "5️⃣ زمان پایان را به صورت تاریخ شمسی وارد کنید\n\n"
        "مثال تاریخ: 1402-12-29 23:59:59"
    )
    await update.message.reply_text(instructions)

async def add_countdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "لطفاً لینک پیام کانال را ارسال کنید.\n"
        "مثال: https://t.me/channelname/123"
    )
    return WAITING_FOR_LINK

async def handle_message_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_link = update.message.text.strip()
    message_info = extract_message_info(message_link)
    
    if not message_info:
        await update.message.reply_text(" لینک پیام نامعتبر است. لطفاً دوباره تلاش کنید یا /cancel را بزنید.")
        return WAITING_FOR_LINK
    
    context.user_data['message_info'] = message_info
    await update.message.reply_text(
        "لطفاً تاریخ و زمان پایان را به صورت شمسی وارد کنید:\n"
        "فرمت: YYYY-MM-DD HH:MM:SS\n"
        "مثال: 1402-12-29 23:59:59"
    )
    return WAITING_FOR_TIME

async def handle_target_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_text = update.message.text.strip()
    
    try:
        # Parse Persian date
        date_parts, time_parts = time_text.split(' ')
        year, month, day = map(int, date_parts.split('-'))
        hour, minute, second = map(int, time_parts.split(':'))
        
        # Convert to Gregorian timestamp
        target_time = JalaliDateTime(year, month, day, hour, minute, second).to_gregorian()
        target_timestamp = target_time.timestamp()
        
        chat_id, message_id = context.user_data['message_info']
        countdown_key = f"{chat_id}_{message_id}"
        
        # Save to JSON
        countdowns = load_countdowns()
        countdowns[countdown_key] = {
            'chat_id': chat_id,
            'message_id': message_id,
            'target_timestamp': target_timestamp
        }
        save_countdowns(countdowns)
        
        # Create countdown job
        create_countdown_job(context.application, chat_id, message_id, target_timestamp)
        
        await update.message.reply_text(" شمارش معکوس با موفقیت شروع شد!")
        
    except Exception as e:
        await update.message.reply_text(
            " فرمت تاریخ نامعتبر است. لطفاً دوباره تلاش کنید یا /cancel را بزنید.\n"
            "مثال صحیح: 1402-12-29 23:59:59"
        )
        return WAITING_FOR_TIME
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(" عملیات لغو شد.")
    return ConversationHandler.END

def main() -> None:
    TOKEN = os.environ.get('TOKEN')
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add_countdown', add_countdown)],
        states={
            WAITING_FOR_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_link)],
            WAITING_FOR_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_target_time)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    
    # Load existing countdowns and create jobs
    countdowns = load_countdowns()
    for countdown_key, data in countdowns.items():
        chat_id = data['chat_id']
        message_id = data['message_id']
        target_timestamp = data['target_timestamp']
        create_countdown_job(application, chat_id, message_id, target_timestamp)
    
    # Start the bot
    print("Starting bot...")
    print(f"Loaded {len(countdowns)} existing countdowns")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

def run_bot():
    main()

if __name__ == '__main__':
    run_bot()
