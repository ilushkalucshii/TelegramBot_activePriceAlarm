import logging
import requests
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
import caller

# Set up logging for debugging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG  # Changed to DEBUG for better debugging visibility
)

TOKEN = "7671917669:AAGdkDKLP2v-F9-Ga3-kg5Vah0EW_CQOf18"

# Store user data (phone, asset, threshold)
user_data = {}

# Function to get Binance assets
def get_binance_assets():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    response = requests.get(url).json()
    if "symbols" in response:
        logging.debug(f"Retrieved Binance assets: {len(response['symbols'])} symbols found.")
        return {symbol["symbol"] for symbol in response["symbols"]}
    logging.warning("No symbols found in Binance response.")
    return set()

# Start command - request phone number from the user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"User {update.message.from_user.id} initiated the /start command.")
    keyboard = [
        [KeyboardButton("Share Phone Number", request_contact=True)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Share your phone number to continue.",
        reply_markup=reply_markup
    )

# Handle phone number sharing
async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone_number = update.message.contact.phone_number
    user_id = update.message.from_user.id
    user_data[user_id] = {"phone_number": phone_number, "threshold": 1.0, "assets": []}

    logging.info(f"User {user_id} shared phone number: {phone_number}")

    # Remove the phone number button and provide the next options
    await update.message.reply_text(
        f"✅ Phone number received: {phone_number}",
        reply_markup=ReplyKeyboardRemove()
    )

    keyboard = [
        [InlineKeyboardButton("Choose Asset", callback_data="choose_asset")],
        [InlineKeyboardButton("Print Following Assets", callback_data="print_following_assets")],
        [InlineKeyboardButton("Change % of Change", callback_data="change_threshold")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Now you can choose the asset and set the % change threshold.",
        reply_markup=reply_markup
    )

# Change threshold callback
async def change_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    logging.debug(f"User {update.callback_query.from_user.id} selected 'Change Threshold'.")

    await query.message.reply_text("Enter the new % change threshold (e.g., 2 for 2%).")

    context.user_data["awaiting_threshold"] = True
    context.user_data["awaiting_asset"] = False

# Choose asset callback
async def choose_asset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    logging.debug(f"User {update.callback_query.from_user.id} selected 'Choose Asset'.")

    await query.message.reply_text("Please enter the asset symbol (e.g., BTCUSDT, ETHUSDT).")

    context.user_data["awaiting_threshold"] = False
    context.user_data["awaiting_asset"] = True

# Handle threshold input from the user
async def handle_threshold_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.debug(f"User {update.message.from_user.id} input threshold: {update.message.text}")

    user_id = update.message.from_user.id
    if "awaiting_threshold" not in context.user_data:
        logging.warning(f"User {user_id} sent input while not awaiting threshold.")
        return

    try:
        threshold = float(update.message.text)
        user_data[user_id]["threshold"] = threshold
        await update.message.reply_text(f"✅ Threshold updated to {threshold}%.")
        context.user_data["awaiting_asset"] = False
        context.user_data["awaiting_threshold"] = False

    except ValueError:
        logging.error(f"Invalid threshold input from user {user_id}: {update.message.text}")
        await update.message.reply_text("⚠️ Please enter a valid number.")

async def handle_asset_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if "awaiting_asset" not in context.user_data:
        return

    asset = update.message.text.upper()
    binance_assets = get_binance_assets()

    if asset in binance_assets:
        threshold = user_data[user_id]["threshold"]

        error = await caller.monitor_price(asset, threshold, user_id, context)

        if isinstance(error, str):  # If an error occurred, send it to Telegram
            await update.message.reply_text(f"⚠️ Error: {error}")
        else:
            user_data[user_id]["assets"].append(asset)
            await update.message.reply_text(
                f"✅ You selected '{asset}'.\n"
                "Now, let's proceed with setting the percentage change threshold."
            )

        context.user_data["awaiting_asset"] = False
        context.user_data["awaiting_threshold"] = False
    else:
        logging.warning(f"User {user_id} tried selecting an invalid asset: {asset}")
        await update.message.reply_text(
            f"⚠️ '{asset}' is not a valid Binance asset.\nPlease check the symbol and try again."
        )

# General input handler, decide whether to handle threshold or asset input
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_asset"):
        await handle_asset_input(update, context)
    if context.user_data.get("awaiting_threshold"):
        await handle_threshold_input(update, context)

# Print the assets being monitored
async def print_assets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.callback_query.from_user.id
    assets = user_data.get(user_id, {}).get("assets", [])

    if assets:
        await query.message.reply_text(f"Following assets are being monitored: {', '.join(assets)} with a threshold of {user_data[user_id]['threshold']}%.")
    else:
        await query.message.reply_text("No assets selected yet.")

# Main function to set up handlers and start the bot
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.CONTACT, handle_phone_number))
    application.add_handler(CallbackQueryHandler(change_threshold, pattern="change_threshold"))
    application.add_handler(CallbackQueryHandler(choose_asset, pattern="choose_asset"))
    application.add_handler(CallbackQueryHandler(print_assets, pattern="print_following_assets"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input, block=True))

    logging.info("Bot started and listening for events.")
    application.run_polling()

if __name__ == "__main__":
    main()
