from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

from datetime import datetime
from persiantools.jdatetime import JalaliDateTime

def remaining_time_from_khayyam(year, month, day, hour, minute, second):
    target_gregorian_datetime = JalaliDateTime(year, month, day, hour, minute, second).to_gregorian()

    current_gregorian_datetime = datetime.now()

    remaining_time = target_gregorian_datetime - current_gregorian_datetime

    remaining_days = remaining_time.days
    remaining_hours, remainder = divmod(remaining_time.seconds, 3600)
    remaining_minutes, remaining_seconds = divmod(remainder, 60)

    return remaining_days, remaining_hours, remaining_minutes, remaining_seconds

#your persian Date time you want count here 
future_khayyam_year = 1402
future_khayyam_month = 12
future_khayyam_day = 17
future_khayyam_hour = 9
future_khayyam_minute = 0
future_khayyam_second = 0

remaining_days, remaining_hours, remaining_minutes, remaining_seconds = remaining_time_from_khayyam(
    future_khayyam_year, future_khayyam_month, future_khayyam_day,
    future_khayyam_hour, future_khayyam_minute, future_khayyam_second
)


def msg(remaining_days, remaining_hours, remaining_minutes, remaining_seconds):
    
    msg = f"🎈زمان باقی مانده تا مسابقه نهایی: {remaining_days} روز, {remaining_hours} ساغت, {remaining_minutes} دقیقه, {remaining_seconds} ثانیه\n"
    return msg


TOKEN = "<YOUR_BOT_TOKEN>"

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hello! I am your bot. Send /time to get day count message.')

def time(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    context.bot.send_message(chat_id, msg(*remaining_time_from_khayyam(
    future_khayyam_year, future_khayyam_month, future_khayyam_day,
    future_khayyam_hour, future_khayyam_minute, future_khayyam_second
)))

def main() -> None:
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("time", time))

    updater.start_polling()

    updater.idle()

if __name__ == '__main__':
    main()

