import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
CMC_API_KEY = os.getenv("CMC_API_KEY")
if not TELEGRAM_API_TOKEN or not CMC_API_KEY:
    raise ValueError("TELEGRAM_API_TOKEN or CMC_API_KEY is not set")

# To track the last time alerts were sent
last_alert_time = None
user_alert_status = {}  # Keeps track of users' stop status and time


# Query CoinMarketCap API
def get_fear_and_greed():
    url = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/latest"
    headers = {
        "X-CMC_PRO_API_KEY": CMC_API_KEY,
    }
    response = requests.get(url, headers=headers).json()
    return response


# Function to send alerts
async def send_alert(context: ContextTypes.DEFAULT_TYPE):
    global last_alert_time
    print("Fetching fear and greed")
    fear_and_greed = get_fear_and_greed()
    value_classification = fear_and_greed["data"]["value_classification"]
    value = fear_and_greed["data"]["value"]
    update_time = fear_and_greed["data"]["update_time"]
    print("Fear and greed data:")
    print(f"Value classification: {value_classification}")
    print(f"Value: {value}")
    print(f"Update time: {update_time}")

    if value_classification in ["Extreme Fear", "Fear", "Neutral"]:
        print(f"Sending alert to users: {user_alert_status}")
        for user_id in user_alert_status:
            if not user_alert_status[user_id]["stop_notifications"]:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🚨 Fear & Greed Index Alert 🚨\n"
                        f"Value classification: {value_classification}\n"
                        f"Value: {value}\n"
                        f"Update time: {update_time} ⏰\n"
                        f"\n"
                        f"Use /stop 12h or /stop 1d to stop alerts for 12 hours or 1 day"
                    ),
                    parse_mode="Markdown",
                )
                last_alert_time = datetime.now()


# Function to handle "/start" command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the Fear & Greed Index Bot! You will receive alerts when the index indicates Extreme Fear or Fear."
    )
    user_alert_status[update.message.chat_id] = {
        "stop_notifications": False,
        "stop_until": None,
    }


# Function to handle "/stop" command to stop alerts for 12 hours or 1 day
async def stop_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Please specify the duration: 12h or 1d.")
        return

    duration = context.args[0]
    stop_until = None
    if duration == "12h":
        stop_until = datetime.now() + timedelta(hours=12)
    elif duration == "1d":
        stop_until = datetime.now() + timedelta(days=1)
    else:
        await update.message.reply_text(
            "Invalid duration. Use '12h' for 12 hours or '1d' for 1 day."
        )
        return

    user_alert_status[update.message.chat_id]["stop_notifications"] = True
    user_alert_status[update.message.chat_id]["stop_until"] = stop_until
    await update.message.reply_text(
        f"Notifications have been paused until {stop_until.strftime('%Y-%m-%d %H:%M:%S')}."
    )


# Function to resume notifications if the time has passed
async def check_resume_notifications(context: ContextTypes.DEFAULT_TYPE):
    global user_alert_status
    for user_id, status in list(user_alert_status.items()):
        if status["stop_notifications"] and status["stop_until"] <= datetime.now():
            user_alert_status[user_id]["stop_notifications"] = False
            await context.bot.send_message(
                chat_id=user_id, text="Notifications have resumed."
            )


# Function to start the bot
def main():
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TELEGRAM_API_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop_alert))

    # Add job queue
    job_queue = application.job_queue
    if job_queue is not None:
        job_queue.run_repeating(
            send_alert, interval=900, first=10
        )  # Run every 15 minutes
        job_queue.run_repeating(
            check_resume_notifications, interval=900, first=0
        )  # Run every 15 minutes
    else:
        print(
            "Warning: Job queue is not available. Alerts will not be sent automatically."
        )

    print("Starting bot")
    # Start the bot
    application.run_polling()


if __name__ == "__main__":
    main()
