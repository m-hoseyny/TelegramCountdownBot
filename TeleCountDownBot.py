from math import e
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters
from datetime import datetime, timezone, timedelta
from persiantools.jdatetime import JalaliDateTime
import asyncio
import json
import re
import os
import logging
import time
from logging.handlers import RotatingFileHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'bot.log',
            maxBytes=1024*1024,  # 1MB
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Constants
WAITING_FOR_LINK = 1
WAITING_FOR_TIME = 2
WAITING_FOR_TEMPLATE = 3

TEMPLATE_PLACEHOLDERS = {
    '{days}': 'روز',
    '{hours}': 'ساعت',
    '{minutes}': 'دقیقه',
    '{seconds}': 'ثانیه'
}

# Database file path
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'countdowns.json')

def load_countdowns():
    try:
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                data = json.load(f)
                logger.info(f"Loaded {len(data)} countdowns from database")
                return data
        logger.warning("Countdown database not found, creating new one")
        return {}
    except Exception as e:
        logger.error(f"Error loading countdowns: {e}")
        return {}

def save_countdowns(countdowns):
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(countdowns, f)
            logger.info(f"Saved {len(countdowns)} countdowns to database")
    except Exception as e:
        logger.error(f"Error saving countdowns: {e}")

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
    else:
        chat_id = '@' + chat_id
    
    return chat_id, message_id

def to_persian_numbers(number):
    """Convert English numbers to Persian numbers"""
    persian_numbers = {
        '0': '۰',
        '1': '۱',
        '2': '۲',
        '3': '۳',
        '4': '۴',
        '5': '۵',
        '6': '۶',
        '7': '۷',
        '8': '۸',
        '9': '۹'
    }
    return ''.join(persian_numbers.get(digit, digit) for digit in str(number))

def calculate_time_components(remaining_seconds):
    """Calculate days, hours, minutes, and seconds from total seconds"""
    if remaining_seconds <= 0:
        return None
        
    days = int(remaining_seconds // (24 * 3600))
    remaining_seconds = remaining_seconds % (24 * 3600)
    hours = int(remaining_seconds // 3600)
    remaining_seconds %= 3600
    minutes = int(remaining_seconds // 60)
    seconds = int(remaining_seconds % 60)
    
    return (
        to_persian_numbers(days),
        to_persian_numbers(hours),
        to_persian_numbers(minutes),
        to_persian_numbers(seconds)
    )

def remaining_time_from_timestamp(target_timestamp):
    """Calculate remaining time from target timestamp"""
    current_time = time.time()
    remaining_seconds = target_timestamp - current_time
    
    if remaining_seconds <= 0:
        return None
        
    return remaining_seconds

def format_countdown_message(remaining_time, template):
    """Format countdown message with Persian numbers"""
    if remaining_time is None:
        return "زمان به پایان رسید!"
        
    time_components = calculate_time_components(remaining_time)
    if time_components is None:
        return "زمان به پایان رسید!"
        
    days, hours, minutes, seconds = time_components
    return template.format(
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds
    )

async def update_single_countdown(context: ContextTypes.DEFAULT_TYPE, countdown_key: str) -> None:
    """Update a single countdown message"""
    logger.debug(f"Updating countdown: {countdown_key}")
    
    try:
        data = get_countdown_data(countdown_key)
        if not data:
            logger.error(f"No data found for countdown {countdown_key}")
            return

        chat_id = data['chat_id']
        message_id = data['message_id']
        target_timestamp = data['target_timestamp']
        template = data.get('template', "زمان باقی مانده:\n<code>{days} روز, {hours} ساعت, {minutes} دقیقه, {seconds} ثانیه</code>")
        admin_chat_id = data.get('admin_chat_id')
        is_caption = data.get('is_caption', False)
        
        remaining_time = remaining_time_from_timestamp(target_timestamp)
        message_text = format_countdown_message(remaining_time, template)
        
        try:
            if is_caption:
                await context.bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=message_text,
                    parse_mode='HTML'
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=message_text,
                    parse_mode='HTML'
                )
        except Exception as e:
            error_msg = str(e).lower()
            if "no text in the message to edit" in error_msg:
                # Update the countdown data to mark it as a caption message
                countdowns = load_countdowns()
                if countdown_key in countdowns:
                    countdowns[countdown_key]['is_caption'] = True
                    save_countdowns(countdowns)
                # Retry with caption
                await context.bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=message_text,
                    parse_mode='HTML'
                )
            elif "message to edit not found" in error_msg or 'chat not found' in error_msg:
                logger.warning(f"Message not found for countdown {countdown_key}, removing from database")
                # Remove the countdown from JSON
                countdowns = load_countdowns()
                if countdown_key in countdowns:
                    del countdowns[countdown_key]
                    save_countdowns(countdowns)
                # Remove the job
                remove_countdown(context.application, countdown_key)
                # Notify admin
                if admin_chat_id:
                    await context.bot.send_message(
                        chat_id=admin_chat_id,
                        text=f"پیام شمارش معکوس پیدا نشد یا پاک شده است. شمارش معکوس متوقف شد.\nشناسه پیام: {countdown_key}",
                        parse_mode='HTML'
                    )
                return
            else:
                raise  # Re-raise if it's a different error
        
        if remaining_time is None:
            # Time's up, stop the countdown
            countdowns = load_countdowns()
            if countdown_key in countdowns:
                del countdowns[countdown_key]
                save_countdowns(countdowns)
            
            remove_countdown(context.application, countdown_key)
            return
            
    except Exception as e:
        logger.error(f"Error updating countdown {countdown_key}: {e}")
        try:
            if admin_chat_id:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f" خطا در بروزرسانی پیام شمارش معکوس. لطفاً مطمئن شوید که ربات ادمین کانال است. \n{e}",
                    parse_mode='HTML'
                )
        except Exception as notify_error:
            logger.error(f"Failed to notify admin about error: {notify_error}")

def remove_countdown(application: Application, countdown_key: str) -> None:
    """Remove a countdown job"""
    current_jobs = application.job_queue.get_jobs_by_name(countdown_key)
    for job in current_jobs:
        job.schedule_removal()

def create_countdown_job(application: Application, countdown_key: str) -> None:
    """Create a new job for a countdown"""
    logger.info(f"Creating job for countdown: {countdown_key}")
    
    # Remove existing jobs for this countdown
    remove_countdown(application, countdown_key)
    
    # Create new job
    application.job_queue.run_repeating(
        callback=lambda context: update_single_countdown(context, countdown_key),
        interval=10,  # Update every 10 seconds
        first=1,  # Start after 1 second
        name=countdown_key
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"Starting new conversation with user {update.effective_user.id}")
    instructions = (
        " سلام! من یک ربات شمارش معکوس هستم.\n\n"
        "برای استفاده از من در کانال خود، لطفا مراحل زیر را دنبال کنید:\n"
        "1️⃣ من را به کانال خود اضافه کنید\n"
        "2️⃣ من را به عنوان ادمین کانال تنظیم کنید\n"
        "3️⃣ یک پیام در کانال ارسال کنید و لینک پیام را کپی کنید\n"
        "4️⃣ دستور /add_countdown را ارسال کنید و لینک پیام را برای من بفرستید\n"
        "5️⃣ زمان پایان را به صورت تاریخ شمسی وارد کنید\n"
        "6️⃣ قالب پیام را با استفاده از متغیرهای زیر وارد کنید:\n\n"
        f"{', '.join(TEMPLATE_PLACEHOLDERS.keys())}\n\n"
        "مثال تاریخ: 1402-12-29 23:59:59\n"
        "مثال قالب پیام: {days} روز و {hours} ساعت و {minutes} دقیقه و {seconds} ثانیه تا شروع مسابقه",
        "\n\nبات از HTML ساپورت میکند!"
    )
    await update.message.reply_text(''.join(instructions), parse_mode='HTML')

async def add_countdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(f"Starting new countdown conversation with user {update.effective_user.id}")
    await update.message.reply_text(
        "لطفاً لینک پیام کانال را ارسال کنید.\n"
        "مثال: https://t.me/channelname/123"
    )
    return WAITING_FOR_LINK

async def handle_message_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        message_link = update.message.text.strip()
        logger.info(f"Received message link: {message_link}")
        message_info = extract_message_info(message_link)
        
        if not message_info:
            await update.message.reply_text(" لینک پیام نامعتبر است. لطفاً دوباره تلاش کنید یا /cancel را بزنید.")
            return WAITING_FOR_LINK
        
        context.user_data['message_info'] = message_info
        context.user_data['message_link'] = message_link.strip()
        await update.message.reply_text(
            "لطفاً تاریخ و زمان پایان را به صورت شمسی وارد کنید:\n"
            "فرمت: YYYY-MM-DD HH:MM:SS\n"
            "مثال:\n"
            "<code>1403-12-29 23:59:59</code>",
            parse_mode='HTML'
        )
        return WAITING_FOR_TIME
        
    except Exception as e:
        logger.error(f"Error processing message link: {e}")
        await update.message.reply_text("لینک نامعتبر است. لطفاً دوباره تلاش کنید یا /cancel را بزنید")
        return WAITING_FOR_LINK

async def handle_target_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        time_text = update.message.text.strip()
        
        # Parse Persian date
        date_parts, time_parts = time_text.split(' ')
        year, month, day = map(int, date_parts.split('-'))
        hour, minute, second = map(int, time_parts.split(':'))
        
        # Convert to Gregorian timestamp
        target_time = JalaliDateTime(year, month, day, hour, minute, second).to_gregorian()
        target_timestamp = target_time.timestamp()
        
        context.user_data['target_timestamp'] = target_timestamp
        
        # Ask for message template
        await update.message.reply_text(
            "لطفاً قالب پیام را وارد کنید. از متغیرهای زیر استفاده کنید:\n"
            f"{', '.join(TEMPLATE_PLACEHOLDERS.keys())}\n\n"
            "مثال:\n"
            "<code>"
            "{days} روز و {hours} ساعت و {minutes} دقیقه و {seconds} ثانیه"
            "\n"
            "تا شروع مسابقه"
            "</code>",
            parse_mode='HTML'
        )
        return WAITING_FOR_TEMPLATE
        
    except Exception as e:
        logger.error(f"Error processing target time: {e}")
        await update.message.reply_text(
            " فرمت تاریخ نامعتبر است. لطفاً دوباره تلاش کنید یا /cancel را بزنید.\n"
            "مثال صحیح: 1402-12-29 23:59:59"
        )
        return WAITING_FOR_TIME

async def handle_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        template = update.message.text.strip()
        
        # Verify template contains all required placeholders
        missing_placeholders = []
        for placeholder in TEMPLATE_PLACEHOLDERS.keys():
            if placeholder not in template:
                missing_placeholders.append(f"{placeholder} ({TEMPLATE_PLACEHOLDERS[placeholder]})")
        
        if missing_placeholders:
            await update.message.reply_text(
                " قالب پیام باید شامل تمام متغیرها باشد. موارد زیر در پیام شما وجود ندارند:\n"
                f"{', '.join(missing_placeholders)}\n\n"
                "لطفاً دوباره تلاش کنید یا /cancel را بزنید."
            )
            return WAITING_FOR_TEMPLATE
        
        chat_id, message_id = context.user_data['message_info']
        target_timestamp = context.user_data['target_timestamp']
        countdown_key = context.user_data['message_link']  # Use the original message link as key
        
        # Save to JSON
        countdowns = load_countdowns()
        countdowns[countdown_key] = {
            'chat_id': chat_id,
            'message_id': message_id,
            'target_timestamp': target_timestamp,
            'template': template,
            "admin_chat_id": update.message.chat_id
        }
        save_countdowns(countdowns)
        
        # Create job for the countdown
        create_countdown_job(context.application, countdown_key)
        
        await update.message.reply_text(" شمارش معکوس با موفقیت شروع شد!")
        
    except Exception as e:
        logger.error(f"Error processing template: {e}")
        await update.message.reply_text(
            " قالب پیام نامعتبر است. لطفاً دوباره تلاش کنید یا /cancel را بزنید."
        )
        return WAITING_FOR_TEMPLATE
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(" عملیات لغو شد.")
    return ConversationHandler.END

def get_countdown_data(countdown_key):
    """Get countdown data from JSON file"""
    countdowns = load_countdowns()
    return countdowns.get(countdown_key)

def main() -> None:
    logger.info("Starting bot...")
    TOKEN = os.environ.get('TOKEN')
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add_countdown', add_countdown)],
        states={
            WAITING_FOR_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_link)],
            WAITING_FOR_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_target_time)],
            WAITING_FOR_TEMPLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_template)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    
    # Load existing countdowns
    countdowns = load_countdowns()
    
    # Create jobs for existing countdowns
    for countdown_key in countdowns:
        create_countdown_job(application, countdown_key)
    
    # Start the bot
    logger.info(f"Loaded {len(countdowns)} existing countdowns")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

def run_bot():
    main()

if __name__ == '__main__':
    run_bot()
